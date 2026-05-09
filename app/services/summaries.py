from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.session import ConversationSession
from app.models.summary import Summary
from app.models.user import User
from app.services.admins import is_admin
from app.services.llm import openrouter_chat


async def build_session_summary(db: AsyncSession, session: ConversationSession, user: User) -> str:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at.asc())
        .limit(60)
    )
    messages = result.scalars().all()
    transcript = "\n".join(
        f"{'Пациент' if m.role == 'user' else 'Оракул'}: {m.content}" for m in messages
    )
    fallback = (
        "Summary беседы\n"
        f"Пользователь: @{user.username or 'без username'}\n"
        f"chat_id: {user.telegram_id}\n\n"
        "Кратко: пользователь взаимодействовал с Оракулом ИИ. "
        "Подробный AI-summary временно недоступен."
    )
    if not transcript.strip():
        return fallback
    try:
        return await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Составь краткое summary беседы для администратора/специалиста. "
                        "Русский язык. 4-7 пунктов: состояние, темы, риски без диагнозов, "
                        "динамика, что стоит уточнить. Не выдумывай факты."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            temperature=0.2,
            max_tokens=700,
        )
    except Exception:
        return fallback + "\n\nФрагмент:\n" + transcript[:1200]


async def create_due_summaries(db: AsyncSession, *, older_than_minutes: int = 60) -> list[Summary]:
    threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
    result = await db.execute(
        select(ConversationSession, User)
        .join(User, User.id == ConversationSession.user_id)
        .where(
            ConversationSession.state != "closed",
            ConversationSession.last_message_at.is_not(None),
            ConversationSession.last_message_at < threshold,
            ConversationSession.summary.is_(None),
        )
        .limit(20)
    )
    created: list[Summary] = []
    for session, user in result.all():
        if is_admin(user):
            session.summary = "Admin session skipped."
            session.state = "closed"
            continue
        text = await build_session_summary(db, session, user)
        session.summary = text
        session.state = "closed"
        summary = Summary(
            session_id=session.id,
            user_id=user.id,
            chat_id=user.telegram_id,
            username=user.username,
            text=text,
        )
        db.add(summary)
        created.append(summary)
    await db.flush()
    return created


async def get_unsent_summaries(db: AsyncSession) -> list[Summary]:
    await create_due_summaries(db)
    result = await db.execute(
        select(Summary).where(Summary.is_sent.is_(False)).order_by(Summary.created_at.asc()).limit(20)
    )
    return list(result.scalars().all())


async def mark_summary_sent(db: AsyncSession, summary_id: UUID) -> None:
    result = await db.execute(select(Summary).where(Summary.id == summary_id))
    summary = result.scalar_one_or_none()
    if summary is None:
        return
    summary.is_sent = True
    summary.sent_at = datetime.now(UTC)
    await db.flush()
