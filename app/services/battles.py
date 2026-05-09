from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.battle import Battle, BattleParticipant
from app.models.message import Message
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.assessment import calculate_status, score_text_locally
from app.services.llm import extract_json_object, openrouter_chat

DEFAULT_BATTLE_TOPIC = (
    "Разберите спорный кейс так, чтобы не победить любой ценой, а сохранить достоинство, "
    "точность аргументации и способность слышать другого."
)


async def generate_battle_topic() -> str:
    try:
        return await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Создай одну тему баттла ETHOS на русском. Тема должна быть короткой, "
                        "спорной, но не экстремистской; проверять субъектность, эмпатию, "
                        "когнитивное смирение и эмоциональный суверенитет. Без markdown."
                    ),
                },
                {"role": "user", "content": "Дай тему для группового баттла."},
            ],
            temperature=0.7,
            max_tokens=180,
        )
    except Exception:
        return DEFAULT_BATTLE_TOPIC


async def create_battle_placeholder(
    db: AsyncSession,
    *,
    user: User,
    chat_id: int | None,
    topic: str | None,
) -> Battle:
    return await create_battle(db, user=user, chat_id=chat_id, topic=topic)


async def create_battle(
    db: AsyncSession,
    *,
    user: User,
    chat_id: int | None,
    topic: str | None,
) -> Battle:
    battle = Battle(
        telegram_chat_id=chat_id,
        created_by_user_id=user.id,
        topic=topic or await generate_battle_topic(),
        status="waiting",
    )
    db.add(battle)
    await db.flush()
    db.add(BattleParticipant(battle_id=battle.id, user_id=user.id, side="initiator"))
    await db.flush()
    return battle


async def get_latest_battle(
    db: AsyncSession,
    *,
    chat_id: int | None,
    statuses: set[str],
) -> Battle | None:
    query = (
        select(Battle)
        .where(Battle.status.in_(statuses))
        .order_by(Battle.created_at.desc())
        .limit(1)
    )
    if chat_id is not None:
        query = query.where(Battle.telegram_chat_id == chat_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def join_waiting_battle(
    db: AsyncSession,
    *,
    user: User,
    chat_id: int | None,
) -> tuple[Battle | None, str]:
    battle = await get_latest_battle(db, chat_id=chat_id, statuses={"waiting"})
    if battle is None:
        return None, "Открытого баттла здесь нет. Запустите: /battle"
    if battle.created_by_user_id == user.id:
        return battle, "Вы уже инициатор этого баттла. Нужен второй участник."

    result = await db.execute(
        select(BattleParticipant).where(
            BattleParticipant.battle_id == battle.id,
            BattleParticipant.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(BattleParticipant(battle_id=battle.id, user_id=user.id, side="challenger"))

    battle.status = "active"
    battle.started_at = datetime.now(UTC)
    await db.flush()
    return (
        battle,
        "Баттл начат.\n\n"
        f"Тема: {battle.topic}\n\n"
        "Пишите аргументы прямо в чат. Когда оба выскажутся, завершите баттл "
        "командой /finishbattle. "
        "Ставка: 1 псикоин.",
    )


async def get_battle_participants(
    db: AsyncSession, battle: Battle
) -> list[tuple[BattleParticipant, User]]:
    result = await db.execute(
        select(BattleParticipant, User)
        .join(User, User.id == BattleParticipant.user_id)
        .where(BattleParticipant.battle_id == battle.id)
        .order_by(BattleParticipant.created_at.asc())
    )
    return list(result.all())


async def collect_battle_messages(
    db: AsyncSession,
    *,
    battle: Battle,
    chat_id: int | None,
    participant_user_ids: list[UUID],
) -> dict[UUID, str]:
    filters = [
        Message.role == "user",
        Message.user_id.in_(participant_user_ids),
    ]
    if battle.started_at is not None:
        filters.append(Message.created_at >= battle.started_at)
    if chat_id is not None:
        filters.append(Message.message_metadata.contains({"chat_id": chat_id}))

    result = await db.execute(
        select(Message).where(*filters).order_by(Message.created_at.asc()).limit(200)
    )
    texts: dict[UUID, list[str]] = {user_id: [] for user_id in participant_user_ids}
    for message in result.scalars().all():
        clean = message.content.strip()
        if not clean or clean.startswith("/"):
            continue
        texts.setdefault(message.user_id, []).append(clean)
    return {user_id: "\n".join(parts) for user_id, parts in texts.items()}


async def judge_battle(
    *,
    topic: str,
    participant_rows: list[tuple[BattleParticipant, User]],
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
            "topic": topic,
            "participants": [
                {
                    "user_id": str(user.id),
                    "username": user.username,
                    "side": participant.side,
                    "text": participant_texts.get(user.id) or "",
                }
                for participant, user in participant_rows
            ],
        }
        raw_text = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — ETHOS-судья группового баттла. Выбери победителя не по агрессии, "
                        "а по субъектности, точности, честности, способности слышать оппонента "
                        "и эмоциональному суверенитету. Верни только JSON: "
                        '{"winner_user_id":"uuid", "scores":{"uuid":0-100}, '
                        '"summary":"краткий вердикт на русском"}.'
                    ),
                },
                {"role": "user", "content": str(payload)},
            ],
            temperature=0.2,
            max_tokens=650,
        )
        raw = extract_json_object(raw_text)
        scores = {
            str(user_id): int(score) for user_id, score in dict(raw.get("scores", {})).items()
        }
        for user_id, score in fallback_scores.items():
            scores.setdefault(user_id, score)
        winner_user_id = str(raw.get("winner_user_id") or max(scores, key=scores.get))
        return {
            "winner_user_id": winner_user_id,
            "scores": scores,
            "summary": str(raw.get("summary") or "Баттл оценен Оракулом."),
            "local": False,
        }
    except Exception as error:
        winner_user_id = max(fallback_scores, key=fallback_scores.get)
        return {
            "winner_user_id": winner_user_id,
            "scores": fallback_scores,
            "summary": (
                "Локальный вердикт: победил участник с более ясной и устойчивой аргументацией."
            ),
            "local": True,
            "error": str(error),
        }


async def finish_active_battle(
    db: AsyncSession,
    *,
    chat_id: int | None,
) -> tuple[Battle | None, str, int]:
    battle = await get_latest_battle(db, chat_id=chat_id, statuses={"active"})
    if battle is None:
        return None, "Активного баттла здесь нет.", 0

    participant_rows = await get_battle_participants(db, battle)
    if len(participant_rows) < 2:
        return battle, "Нужны два участника. Второй может войти командой /joinbattle.", 0

    user_ids = [user.id for _, user in participant_rows]
    participant_texts = await collect_battle_messages(
        db,
        battle=battle,
        chat_id=chat_id,
        participant_user_ids=user_ids,
    )
    verdict = await judge_battle(
        topic=battle.topic,
        participant_rows=participant_rows,
        participant_texts=participant_texts,
    )

    rows_by_user = {user.id: (participant, user) for participant, user in participant_rows}
    try:
        winner_id = UUID(str(verdict["winner_user_id"]))
    except (TypeError, ValueError):
        winner_id = None
    if winner_id not in rows_by_user:
        winner_id = max(
            (user.id for _, user in participant_rows),
            key=lambda user_id: int(verdict["scores"].get(str(user_id), 0)),
        )
    loser_ids = [user.id for _, user in participant_rows if user.id != winner_id]
    loser_id = loser_ids[0]
    winner_participant, winner = rows_by_user[winner_id]
    loser_participant, loser = rows_by_user[loser_id]

    for participant, user in participant_rows:
        score = int(verdict["scores"].get(str(user.id), 0))
        participant.score = score
        previous = user.subjectivity_score
        user.subjectivity_score = round((previous * 0.7) + (score * 0.3))
        bonus = 0
        if previous > 0 and score - previous >= 8:
            bonus = 1 if score - previous < 18 else 2
            user.token_balance += bonus
            db.add(
                TokenLedgerEntry(
                    user_id=user.id,
                    amount=bonus,
                    reason=f"PsyCoin battle improvement bonus: {battle.id}",
                )
            )
        user.status = calculate_status(user.subjectivity_score, user.token_balance)

    stake = min(1, loser.token_balance)
    if stake:
        loser.token_balance -= stake
        db.add(
            TokenLedgerEntry(
                user_id=loser.id,
                amount=-stake,
                reason=f"PsyCoin battle stake lost: {battle.id}",
            )
        )
    winner_gain = stake or 1
    winner.token_balance += winner_gain
    db.add(
        TokenLedgerEntry(
            user_id=winner.id,
            amount=winner_gain,
            reason=f"PsyCoin battle victory: {battle.id}",
        )
    )

    winner.status = calculate_status(winner.subjectivity_score, winner.token_balance)
    loser.status = calculate_status(loser.subjectivity_score, loser.token_balance)
    battle.status = "finished"
    battle.finished_at = datetime.now(UTC)
    battle.result_summary = verdict["summary"]
    await db.flush()

    winner_name = (
        f"@{winner.username}" if winner.username else winner.first_name or str(winner.telegram_id)
    )
    loser_name = (
        f"@{loser.username}" if loser.username else loser.first_name or str(loser.telegram_id)
    )
    reply = (
        "Баттл завершен.\n\n"
        f"Тема: {battle.topic}\n\n"
        f"Победитель: {winner_name}\n"
        f"Ставка: +{winner_gain} псикоин победителю"
        + (f", -{stake} псикоин у {loser_name}" if stake else " из резерва системы")
        + "\n\n"
        f"{verdict['summary']}\n\n"
        "Оценки:\n"
        + "\n".join(
            f"{('@' + user.username) if user.username else user.first_name or user.telegram_id}: "
            f"{participant.score}/100"
            for participant, user in participant_rows
        )
    )
    return battle, reply, winner_gain
