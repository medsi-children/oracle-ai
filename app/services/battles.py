from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.battle import Battle, BattleParticipant
from app.models.marketplace import MarketplaceItem, MarketplacePurchase
from app.models.message import Message
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.assessment import (
    calculate_status,
    refresh_user_profile_summary,
    score_text_locally,
)
from app.services.llm import extract_json_object, openrouter_chat
from app.services.phrasing import psycoins

BATTLE_ENTRY_OPTIONS = [1, 3, 5, 10, 50, 100]
COLLECTIBLE_BATTLE_BUFFS = {
    "✨ Искра Осознания": 3,
    "🔥 Пламя Безмятежности": 5,
    "🪞 Зеркало Искренности": 8,
    "Знак Искренности": 8,
    "💍 Серебряный Перстень": 11,
    "🦊 Золотой Лис": 14,
    "💎 Бриллиантовое Сердце": 18,
}
DEFAULT_BATTLE_TOPIC = (
    "Разберите спорный кейс так, чтобы не победить шумом, а удержать позицию, "
    "конкретику, контроль реакции и способность видеть последствия."
)


@dataclass(frozen=True)
class BattleItemBuff:
    item_title: str | None = None
    percent: int = 0


@dataclass(frozen=True)
class BattleScoreBreakdown:
    base_score: int
    buff: BattleItemBuff
    bonus_points: int
    final_score: int


def user_public_name(user: User) -> str:
    return f"@{user.username}" if user.username else user.first_name or str(user.telegram_id)


def clamp_score(score: int) -> int:
    return max(0, min(100, int(score)))


def collectible_battle_buff_percent(item: MarketplaceItem) -> int:
    if item.item_type != "collectible":
        return 0
    return COLLECTIBLE_BATTLE_BUFFS.get(item.title, 0)


def apply_collectible_battle_buff(
    base_score: int, buff: BattleItemBuff
) -> BattleScoreBreakdown:
    base_score = clamp_score(base_score)
    if buff.percent <= 0:
        return BattleScoreBreakdown(
            base_score=base_score,
            buff=BattleItemBuff(),
            bonus_points=0,
            final_score=base_score,
        )
    bonus_points = int((base_score * buff.percent / 100) + 0.5)
    final_score = min(100, base_score + bonus_points)
    return BattleScoreBreakdown(
        base_score=base_score,
        buff=buff,
        bonus_points=final_score - base_score,
        final_score=final_score,
    )


async def get_collectible_battle_buffs(
    db: AsyncSession, user_ids: list[UUID]
) -> dict[UUID, BattleItemBuff]:
    if not user_ids:
        return {}
    result = await db.execute(
        select(MarketplacePurchase.user_id, MarketplaceItem)
        .join(MarketplaceItem, MarketplaceItem.id == MarketplacePurchase.item_id)
        .where(
            MarketplacePurchase.user_id.in_(user_ids),
            MarketplaceItem.item_type == "collectible",
            MarketplaceItem.is_active.is_(True),
        )
    )
    buffs: dict[UUID, BattleItemBuff] = {user_id: BattleItemBuff() for user_id in user_ids}
    for user_id, item in result.all():
        percent = collectible_battle_buff_percent(item)
        current = buffs.get(user_id, BattleItemBuff())
        if percent > current.percent:
            buffs[user_id] = BattleItemBuff(item_title=item.title, percent=percent)
    return buffs


def format_score_breakdown(name: str, breakdown: BattleScoreBreakdown) -> str:
    if breakdown.bonus_points <= 0:
        return f"{name}: {breakdown.base_score}/100"
    return (
        f"{name}: {breakdown.base_score} + {breakdown.bonus_points} "
        f"за трофей «{breakdown.buff.item_title}» "
        f"(+{breakdown.buff.percent}%) = {breakdown.final_score}/100"
    )


def choose_battle_winner_id(
    user_ids: list[UUID],
    score_breakdowns: dict[UUID, BattleScoreBreakdown],
    oracle_winner_id: UUID | None,
) -> UUID:
    return max(
        user_ids,
        key=lambda user_id: (
            score_breakdowns[user_id].final_score,
            score_breakdowns[user_id].base_score,
            1 if user_id == oracle_winner_id else 0,
        ),
    )


async def generate_battle_topic() -> str:
    try:
        return await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Создай одну тему баттла ETHOS на русском. "
                        "Тема должна быть короткой, спорной, но не экстремистской; "
                        "проверять субъектность, эмпатию, проверку реальности и "
                        "контроль реакции под давлением. Без markdown."
                    ),
                },
                {"role": "user", "content": "Дай тему для группового баттла."},
            ],
            temperature=0.7,
            max_tokens=180,
        )
    except Exception:
        return DEFAULT_BATTLE_TOPIC


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
        status="configuring",
    )
    db.add(battle)
    await db.flush()
    return battle


async def get_latest_battle(
    db: AsyncSession,
    *,
    chat_id: int | None,
    statuses: set[str],
    created_by_user_id: UUID | None = None,
) -> Battle | None:
    query = (
        select(Battle)
        .where(Battle.status.in_(statuses))
        .order_by(Battle.created_at.desc())
        .limit(1)
    )
    if chat_id is not None:
        query = query.where(Battle.telegram_chat_id == chat_id)
    if created_by_user_id is not None:
        query = query.where(Battle.created_by_user_id == created_by_user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_battle_by_id(db: AsyncSession, battle_id: UUID) -> Battle | None:
    result = await db.execute(select(Battle).where(Battle.id == battle_id))
    return result.scalar_one_or_none()


async def choose_battle_entry_fee(
    db: AsyncSession,
    *,
    battle: Battle,
    user: User,
    entry_fee: int,
) -> tuple[bool, str]:
    if battle.status != "configuring":
        return False, "Этот баттл уже настроен или завершен."
    if battle.created_by_user_id != user.id:
        return False, "Уровень баттла выбирает тот, кто его открыл."
    if entry_fee < 1 or entry_fee > 100:
        return False, "Уровень баттла должен быть от 1 до 100 псикоинов."
    if user.token_balance < entry_fee:
        return (
            False,
            f"Для этого уровня нужно {psycoins(entry_fee)}. Сейчас у вас {psycoins(user.token_balance)}.",
        )

    user.token_balance -= entry_fee
    battle.entry_fee = entry_fee
    battle.reward_tokens = entry_fee
    battle.status = "waiting"
    db.add(
        BattleParticipant(
            battle_id=battle.id,
            user_id=user.id,
            side="initiator",
            entry_fee=entry_fee,
        )
    )
    db.add(
        TokenLedgerEntry(
            user_id=user.id,
            amount=-entry_fee,
            reason=f"PsyCoin battle participation fee: {battle.id}",
        )
    )
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    await db.flush()
    return True, format_battle_waiting_message(battle)


def format_battle_waiting_message(battle: Battle) -> str:
    return (
        "Баттл настроен.\n\n"
        f"Тема: {battle.topic}\n\n"
        f"Уровень участия: {psycoins(battle.entry_fee)}.\n"
        "Победитель получает возврат взноса и такую же награду от системы.\n\n"
        "Коллекционные трофеи дают мягкий бафф к оценке: применяется самый сильный, "
        "максимум +18%.\n\n"
        "Нужен второй участник."
    )


async def join_waiting_battle(
    db: AsyncSession,
    *,
    user: User,
    chat_id: int | None,
    battle_id: UUID | None = None,
) -> tuple[Battle | None, str]:
    battle = (
        await get_battle_by_id(db, battle_id)
        if battle_id is not None
        else await get_latest_battle(db, chat_id=chat_id, statuses={"waiting"})
    )
    if battle is None or battle.status != "waiting":
        return None, "Открытого баттла здесь нет. Запустите: /battle"
    if battle.created_by_user_id == user.id:
        return battle, "Вы уже инициатор этого баттла. Нужен второй участник."

    result = await db.execute(
        select(BattleParticipant).where(
            BattleParticipant.battle_id == battle.id,
            BattleParticipant.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return battle, "Вы уже зарегистрированы в этом баттле."

    entry_fee = battle.entry_fee or 1
    if user.token_balance < entry_fee:
        return (
            battle,
            f"Для входа нужно {psycoins(entry_fee)}. Сейчас у вас {psycoins(user.token_balance)}.",
        )

    user.token_balance -= entry_fee
    db.add(
        BattleParticipant(
            battle_id=battle.id,
            user_id=user.id,
            side="challenger",
            entry_fee=entry_fee,
        )
    )
    db.add(
        TokenLedgerEntry(
            user_id=user.id,
            amount=-entry_fee,
            reason=f"PsyCoin battle participation fee: {battle.id}",
        )
    )
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    battle.status = "active"
    battle.started_at = datetime.now(UTC)
    await db.flush()
    return (
        battle,
        "Баттл начат.\n\n"
        f"Тема: {battle.topic}\n\n"
        f"Уровень участия: {psycoins(entry_fee)}.\n"
        "Пишите аргументы прямо в чат. Когда позиции раскрыты, завершите баттл.\n\n"
        "Если у участника есть коллекционный трофей, Оракул покажет его бафф в финальном счете.",
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
        if message.message_metadata.get("callback_data"):
            continue
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
                        "Ты ETHOS-судья баттла. Выбери победителя по навыку: "
                        "точность аргумента, честность, субъектность, способность слышать "
                        "оппонента, контроль реакции и готовность назвать конкретный шаг и последствия. "
                        "Не выбирай по агрессии, громкости или красивому лозунгу. "
                        "Добавь короткий комментарий Оракула: не инструкция как отвечать, "
                        "а фиксация одного главного паттерна в аргументах обоих участников. "
                        "Если слабость общая, скажи про обоих; если различие заметно, обозначь "
                        "его без унижения. Без туманных формулировок и пафоса. "
                        "Верни только JSON: "
                        '{"winner_user_id":"uuid", "scores":{"uuid":0-100}, '
                        '"summary":"краткий вердикт на русском", '
                        '"oracle_comment":"короткий комментарий Оракула"}.'
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
            "oracle_comment": str(raw.get("oracle_comment") or "").strip(),
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
            "oracle_comment": (
                "Комментарий Оракула: в финальной оценке выше ценится конкретика, контроль реакции "
                "и готовность назвать конкретный шаг и последствия."
            ),
            "local": True,
            "error": str(error),
        }


async def finish_active_battle(
    db: AsyncSession,
    *,
    chat_id: int | None,
    battle_id: UUID | None = None,
) -> tuple[Battle | None, str, int]:
    battle = (
        await get_battle_by_id(db, battle_id)
        if battle_id is not None
        else await get_latest_battle(db, chat_id=chat_id, statuses={"active"})
    )
    if battle is None or battle.status != "active":
        return None, "Активного баттла здесь нет.", 0

    participant_rows = await get_battle_participants(db, battle)
    if len(participant_rows) < 2:
        return battle, "Нужны два участника. Второй может войти кнопкой регистрации.", 0

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
    buffs_by_user = await get_collectible_battle_buffs(db, user_ids)
    score_breakdowns: dict[UUID, BattleScoreBreakdown] = {}
    for _participant, user in participant_rows:
        base_score = clamp_score(int(verdict["scores"].get(str(user.id), 0)))
        score_breakdowns[user.id] = apply_collectible_battle_buff(
            base_score,
            buffs_by_user.get(user.id, BattleItemBuff()),
        )

    try:
        oracle_winner_id = UUID(str(verdict["winner_user_id"]))
    except (TypeError, ValueError):
        oracle_winner_id = None
    winner_id = choose_battle_winner_id(user_ids, score_breakdowns, oracle_winner_id)
    winner_participant, winner = rows_by_user[winner_id]

    for participant, user in participant_rows:
        score = score_breakdowns[user.id].base_score
        # В БД храним базовую оценку навыка: трофеи влияют на исход баттла,
        # но не на индекс субъектности.
        participant.score = score
        previous = user.subjectivity_score
        user.subjectivity_score = round((previous * 0.7) + (score * 0.3))
        user.status = calculate_status(user.subjectivity_score, user.token_balance)
        await refresh_user_profile_summary(
            db,
            user=user,
            event_summary=verdict["summary"],
            event_source="battle",
            event_score=score,
        )

    winner_return = winner_participant.entry_fee or battle.entry_fee or 1
    winner_reward = battle.reward_tokens or winner_return
    winner_gain = winner_return + winner_reward
    winner.token_balance += winner_gain
    winner.status = calculate_status(winner.subjectivity_score, winner.token_balance)
    db.add(
        TokenLedgerEntry(
            user_id=winner.id,
            amount=winner_gain,
            reason=f"PsyCoin battle winner refund and award: {battle.id}",
        )
    )

    battle.status = "finished"
    battle.finished_at = datetime.now(UTC)
    battle.result_summary = verdict["summary"]
    await db.flush()

    oracle_comment = str(verdict.get("oracle_comment") or "").strip()
    oracle_comment_block = f"\n\nКомментарий Оракула:\n{oracle_comment}" if oracle_comment else ""
    reply = (
        "Баттл завершен.\n\n"
        f"Тема: {battle.topic}\n\n"
        f"Победитель: {user_public_name(winner)}\n"
        f"Возврат взноса: {psycoins(winner_return)}\n"
        f"Награда системы: {psycoins(winner_reward)}\n\n"
        f"{verdict['summary']}"
        f"{oracle_comment_block}\n\n"
        "Оценки:\n"
        + "\n".join(
            format_score_breakdown(user_public_name(user), score_breakdowns[user.id])
            for _participant, user in participant_rows
        )
    )
    return battle, reply, winner_gain
