from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.message import Message
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.daily_tasks import AUTOMATED_MESSAGE_LIFECYCLES
from app.services.llm import clean_generated_text, openrouter_chat
from app.services.phrasing import psycoins
from app.services.telegram_delivery import send_message


def _assessment_line(assessment: Assessment) -> str:
    return (
        f"{assessment.created_at:%Y-%m-%d} {assessment.source}: "
        f"субъектность {assessment.subjectivity}/100, честность {assessment.honesty}/100, "
        f"контроль реакции {assessment.emotional_sovereignty}/100, проверка реальности "
        f"{assessment.cognitive_humility}/100, эмпатия {assessment.empathy}/100. "
        f"Вывод: {assessment.summary}"
    )


async def generate_weekly_report(db: AsyncSession, user: User) -> str:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    assessment_result = await db.execute(
        select(Assessment)
        .where(Assessment.user_id == user.id)
        .order_by(Assessment.created_at.asc())
        .limit(120)
    )
    assessments = list(assessment_result.scalars().all())
    week_assessments = [
        assessment
        for assessment in assessments
        if assessment.created_at is not None
        and (assessment.created_at if assessment.created_at.tzinfo else assessment.created_at.replace(tzinfo=UTC))
        >= week_ago
    ]

    message_result = await db.execute(
        select(Message)
        .where(Message.user_id == user.id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(40)
    )
    recent_messages: list[str] = []
    for message in message_result.scalars().all():
        if message.message_metadata.get("callback_data"):
            continue
        text = message.content.strip()
        if not text or text.startswith("/"):
            continue
        recent_messages.append(text)
        if len(recent_messages) >= 20:
            break

    token_result = await db.execute(
        select(TokenLedgerEntry)
        .where(TokenLedgerEntry.user_id == user.id, TokenLedgerEntry.created_at >= week_ago)
        .order_by(TokenLedgerEntry.created_at.asc())
    )
    weekly_tokens = sum(entry.amount for entry in token_result.scalars().all())

    first_score = assessments[0].subjectivity if assessments else user.subjectivity_score
    last_score = assessments[-1].subjectivity if assessments else user.subjectivity_score
    week_first = week_assessments[0].subjectivity if week_assessments else None
    week_last = week_assessments[-1].subjectivity if week_assessments else None

    fallback = (
        "Недельный вердикт ETHOS\n\n"
        "Данных пока мало для точной динамики. На этой неделе важно не набирать правильные "
        "фразы, а фиксировать свои реальные решения: где ты взял управление, где ушел в "
        "автоматическую реакцию, где выбрал действие вместо объяснения.\n\n"
        f"Текущий индекс субъектности: {user.subjectivity_score}/100.\n"
        f"Баланс за неделю: {psycoins(weekly_tokens)}."
    )

    try:
        raw = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — Оракул ETHOS. Составь недельный вердикт по динамике пользователя. "
                        "Пиши прямо и понятно: где человек усилил субъектность, где повторяет "
                        "старый паттерн, какие расхождения между принципами и действиями видны, "
                        "какой навык тренировать дальше. Без туманных формулировок, "
                        "без markdown, без лести и без медицинских выводов. Тон сухой, точный, "
                        "1 заголовок и 4 коротких блока: Что изменилось, Где ты теряешь управление, "
                        "Сильный ход недели, Фокус следующей недели."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Пользователь: @{user.username or 'без username'}\n"
                        f"Текущий статус: {user.status}\n"
                        f"Текущий индекс: {user.subjectivity_score}/100\n"
                        f"Изменение за все время по оценкам: {first_score} -> {last_score}\n"
                        f"Изменение за неделю: {week_first} -> {week_last}\n"
                        f"Токены за неделю: {weekly_tokens}\n\n"
                        f"Профиль:\n{user.profile_summary or 'Профиль пока формируется.'}\n\n"
                        f"Оценки за неделю:\n{chr(10).join(_assessment_line(a) for a in week_assessments) or 'Оценок за неделю нет.'}\n\n"
                        f"Последние оценки за все время:\n{chr(10).join(_assessment_line(a) for a in assessments[-12:]) or 'Оценок пока нет.'}\n\n"
                        f"Последние ответы:\n{chr(10).join(reversed(recent_messages)) or 'Ответов пока нет.'}"
                    ),
                },
            ],
            temperature=0.25,
            max_tokens=900,
        )
        return clean_generated_text(raw, split_sections=True)
    except Exception:
        return fallback


async def send_weekly_reports_to_all_users() -> int:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.lifecycle_status.in_(AUTOMATED_MESSAGE_LIFECYCLES),
                User.telegram_id.is_not(None),
            )
        )
        users = result.scalars().all()
        sent = 0
        for user in users:
            try:
                report = await generate_weekly_report(db, user)
                await send_message(chat_id=int(user.telegram_id), text=report)
                sent += 1
            except Exception:
                continue
        return sent
