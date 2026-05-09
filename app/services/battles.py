from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.battle import Battle, BattleParticipant
from app.models.user import User


async def create_battle_placeholder(
    db: AsyncSession,
    *,
    user: User,
    chat_id: int | None,
    topic: str | None,
) -> Battle:
    battle = Battle(
        telegram_chat_id=chat_id,
        created_by_user_id=user.id,
        topic=topic
        or (
            "Участники должны разобрать спорный кейс так, чтобы не победить любой ценой, "
            "а сохранить достоинство, точность аргументации и способность слышать другого."
        ),
        status="waiting",
    )
    db.add(battle)
    await db.flush()
    db.add(BattleParticipant(battle_id=battle.id, user_id=user.id, side="initiator"))
    await db.flush()
    return battle
