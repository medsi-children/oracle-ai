from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.group_activity import GroupDiscussion, GroupDiscussionParticipant
from app.models.message import Message
from app.models.news import NewsItem
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.assessment import (
    calculate_status,
    refresh_user_profile_summary,
    score_text_locally,
)
from app.services.battles import user_public_name
from app.services.llm import extract_json_object, openrouter_chat
from app.services.phrasing import psycoins

DISCUSSION_ENTRY_OPTIONS = [1, 3, 5, 10, 50, 100]


async def create_case_discussion(
    db: AsyncSession,
    *,
    user: User,
    chat_id: int | None,
    case: Case,
) -> GroupDiscussion:
    discussion = GroupDiscussion(
        telegram_chat_id=chat_id,
        discussion_type="case",
        status="active",
        title=case.title,
        prompt=case.prompt,
        created_by_user_id=user.id,
        case_id=case.id,
        started_at=datetime.now(UTC),
    )
    db.add(discussion)
    await db.flush()
    return discussion


async def create_news_discussion(
    db: AsyncSession,
    *,
    user: User,
    chat_id: int | None,
    item: NewsItem,
) -> GroupDiscussion:
    discussion = GroupDiscussion(
        telegram_chat_id=chat_id,
        discussion_type="news",
        status="active",
        title=item.title[:300],
        prompt=item.ethical_case,
        created_by_user_id=user.id,
        news_item_id=item.id,
        started_at=datetime.now(UTC),
    )
    db.add(discussion)
    await db.flush()
    return discussion


async def get_discussion_by_id(
    db: AsyncSession, discussion_id: UUID
) -> GroupDiscussion | None:
    result = await db.execute(select(GroupDiscussion).where(GroupDiscussion.id == discussion_id))
    return result.scalar_one_or_none()


async def get_latest_discussion(
    db: AsyncSession,
    *,
    chat_id: int | None,
    statuses: set[str],
) -> GroupDiscussion | None:
    query = (
        select(GroupDiscussion)
        .where(GroupDiscussion.status.in_(statuses))
        .order_by(GroupDiscussion.created_at.desc())
        .limit(1)
    )
    if chat_id is not None:
        query = query.where(GroupDiscussion.telegram_chat_id == chat_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


def format_discussion_prompt(discussion: GroupDiscussion) -> str:
    heading = "ETHOS-кейс" if discussion.discussion_type == "case" else "Sentinel Mode"
    return (
        f"{heading}\n\n"
        f"{discussion.prompt}\n\n"
        "Чтобы участвовать в разборе, выберите уровень участия. "
        "В конце Оракул отметит три лучших вклада: точность, честность, глубину и "
        "способность видеть другую сторону."
    )


async def join_discussion(
    db: AsyncSession,
    *,
    discussion: GroupDiscussion,
    user: User,
    entry_fee: int,
) -> tuple[bool, str]:
    if discussion.status != "active":
        return False, "Это обсуждение уже закрыто."
    if entry_fee not in DISCUSSION_ENTRY_OPTIONS:
        return False, "Такого уровня участия нет."

    result = await db.execute(
        select(GroupDiscussionParticipant).where(
            GroupDiscussionParticipant.discussion_id == discussion.id,
            GroupDiscussionParticipant.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return False, "Вы уже участвуете в этом обсуждении. Пишите аргумент в чат."
    if user.token_balance < entry_fee:
        return (
            False,
            f"Для входа нужно {psycoins(entry_fee)}. Сейчас у вас {psycoins(user.token_balance)}.",
        )

    user.token_balance -= entry_fee
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    db.add(
        GroupDiscussionParticipant(
            discussion_id=discussion.id,
            user_id=user.id,
            entry_fee=entry_fee,
        )
    )
    db.add(
        TokenLedgerEntry(
            user_id=user.id,
            amount=-entry_fee,
            reason=f"PsyCoin discussion participation fee: {discussion.id}",
        )
    )
    await db.flush()
    return (
        True,
        f"Участие принято: {psycoins(entry_fee)}.\n\n"
        "Теперь напишите позицию прямо в чат. Оракул учтет только сообщения участников.",
    )


async def get_discussion_participants(
    db: AsyncSession, discussion: GroupDiscussion
) -> list[tuple[GroupDiscussionParticipant, User]]:
    result = await db.execute(
        select(GroupDiscussionParticipant, User)
        .join(User, User.id == GroupDiscussionParticipant.user_id)
        .where(GroupDiscussionParticipant.discussion_id == discussion.id)
        .order_by(GroupDiscussionParticipant.created_at.asc())
    )
    return list(result.all())


async def collect_discussion_messages(
    db: AsyncSession,
    *,
    discussion: GroupDiscussion,
    chat_id: int | None,
    participant_user_ids: list[UUID],
) -> dict[UUID, str]:
    filters = [
        Message.role == "user",
        Message.user_id.in_(participant_user_ids),
    ]
    if discussion.started_at is not None:
        filters.append(Message.created_at >= discussion.started_at)
    if chat_id is not None:
        filters.append(Message.message_metadata.contains({"chat_id": chat_id}))

    result = await db.execute(
        select(Message).where(*filters).order_by(Message.created_at.asc()).limit(300)
    )
    texts: dict[UUID, list[str]] = {user_id: [] for user_id in participant_user_ids}
    for message in result.scalars().all():
        if message.message_metadata.get("callback_data"):
            continue
        clean = message.content.strip()
        if not clean or clean.startswith("/"):
            continue
        texts.setdefault(message.user_id, []).append(clean)
    return {user_id: "\n".join(parts) for user_id, parts in texts.items()}


async def judge_discussion(
    *,
    discussion: GroupDiscussion,
    participant_rows: list[tuple[GroupDiscussionParticipant, User]],
    participant_texts: dict[UUID, str],
) -> dict:
    fallback_scores: dict[str, int] = {}
    for _participant, user in participant_rows:
        text = participant_texts.get(user.id) or ""
        result = score_text_locally(text or "Позиция не раскрыта.", implicit_signals=None)
        fallback_scores[str(user.id)] = round(
            (
                result.subjectivity
                + result.honesty
                + result.emotional_sovereignty
                + result.cognitive_humility
                + result.empathy
            )
            / 5
        )

    try:
        payload = {
            "type": discussion.discussion_type,
            "prompt": discussion.prompt,
            "participants": [
                {
                    "user_id": str(user.id),
                    "username": user.username,
                    "text": participant_texts.get(user.id) or "",
                }
                for _participant, user in participant_rows
            ],
        }
        raw_text = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты ETHOS-судья группового обсуждения. Выбери до трех лучших вкладов "
                        "по навыку: точность, честность, глубина, когнитивное смирение, "
                        "эмпатия, отсутствие лозунгов и способность видеть другую сторону. "
                        "Верни только JSON: "
                        '{"winner_user_ids":["uuid"], "scores":{"uuid":0-100}, '
                        '"summary":"краткий вердикт на русском"}.'
                    ),
                },
                {"role": "user", "content": str(payload)},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        raw = extract_json_object(raw_text)
        scores = {
            str(user_id): int(score) for user_id, score in dict(raw.get("scores", {})).items()
        }
        for user_id, score in fallback_scores.items():
            scores.setdefault(user_id, score)
        winner_ids = [
            str(user_id)
            for user_id in list(raw.get("winner_user_ids") or [])
            if str(user_id) in scores
        ]
        if not winner_ids:
            winner_ids = sorted(scores, key=scores.get, reverse=True)
        return {
            "winner_user_ids": winner_ids[:3],
            "scores": scores,
            "summary": str(raw.get("summary") or "Обсуждение оценено Оракулом."),
            "local": False,
        }
    except Exception as error:
        winner_ids = sorted(fallback_scores, key=fallback_scores.get, reverse=True)
        return {
            "winner_user_ids": winner_ids[:3],
            "scores": fallback_scores,
            "summary": (
                "Локальный вердикт: выше оценены более ясные, честные и устойчивые позиции."
            ),
            "local": True,
            "error": str(error),
        }


def discussion_award_for_rank(entry_fee: int, rank: int) -> int:
    if rank == 1:
        return entry_fee * 3
    if rank == 2:
        return entry_fee * 2
    if rank == 3:
        return entry_fee
    return 0


async def finish_discussion(
    db: AsyncSession,
    *,
    chat_id: int | None,
    discussion_id: UUID | None = None,
) -> tuple[GroupDiscussion | None, str, int]:
    discussion = (
        await get_discussion_by_id(db, discussion_id)
        if discussion_id is not None
        else await get_latest_discussion(db, chat_id=chat_id, statuses={"active"})
    )
    if discussion is None or discussion.status != "active":
        return None, "Активного обсуждения здесь нет.", 0

    participant_rows = await get_discussion_participants(db, discussion)
    if len(participant_rows) < 2:
        return discussion, "Для завершения нужны минимум два участника обсуждения.", 0

    user_ids = [user.id for _, user in participant_rows]
    participant_texts = await collect_discussion_messages(
        db,
        discussion=discussion,
        chat_id=chat_id,
        participant_user_ids=user_ids,
    )
    verdict = await judge_discussion(
        discussion=discussion,
        participant_rows=participant_rows,
        participant_texts=participant_texts,
    )
    rows_by_user = {user.id: (participant, user) for participant, user in participant_rows}
    ranked_ids: list[UUID] = []
    for raw_id in verdict["winner_user_ids"]:
        try:
            user_id = UUID(str(raw_id))
        except (TypeError, ValueError):
            continue
        if user_id in rows_by_user and user_id not in ranked_ids:
            ranked_ids.append(user_id)

    awarded_total = 0
    winners: list[str] = []
    for rank, user_id in enumerate(ranked_ids[:3], start=1):
        participant, user = rows_by_user[user_id]
        participant.rank = rank
        award = discussion_award_for_rank(participant.entry_fee, rank)
        participant.score = int(verdict["scores"].get(str(user.id), 0))
        user.token_balance += award
        user.status = calculate_status(user.subjectivity_score, user.token_balance)
        awarded_total += award
        db.add(
            TokenLedgerEntry(
                user_id=user.id,
                amount=award,
                reason=f"PsyCoin discussion rank {rank} award: {discussion.id}",
            )
        )
        winners.append(f"{rank}. {user_public_name(user)}: +{psycoins(award)}")

    for participant, user in participant_rows:
        participant.score = int(verdict["scores"].get(str(user.id), participant.score))
        previous = user.subjectivity_score
        user.subjectivity_score = round((previous * 0.8) + (participant.score * 0.2))
        user.status = calculate_status(user.subjectivity_score, user.token_balance)
        await refresh_user_profile_summary(
            db,
            user=user,
            event_summary=verdict["summary"],
            event_source=f"group_{discussion.discussion_type}",
            event_score=participant.score,
        )

    discussion.status = "finished"
    discussion.finished_at = datetime.now(UTC)
    discussion.result_summary = verdict["summary"]
    await db.flush()

    heading = "Кейс завершен." if discussion.discussion_type == "case" else "Новостной разбор завершен."
    reply = (
        f"{heading}\n\n"
        f"{verdict['summary']}\n\n"
        "Лучшие вклады:\n"
        + "\n".join(winners)
        + "\n\nОценки:\n"
        + "\n".join(
            f"{user_public_name(user)}: {participant.score}/100"
            for participant, user in participant_rows
        )
    )
    return discussion, reply, awarded_total
