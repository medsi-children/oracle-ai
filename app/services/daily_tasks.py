from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.session import ConversationSession
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.assessment import (
    analyze_implicit_signals,
    assessment_average_score,
    calculate_status,
    create_assessment,
)
from app.services.llm import clean_generated_text, openrouter_chat
from app.services.phrasing import psycoins
from app.services.telegram_delivery import send_message

MORNING_QUESTION_PREFIX = (
    "У Оракула для вас вопрос. Ответьте на него и заработаете псикоины."
)
FORBIDDEN_MORNING_TERMS = ("субъект", "объект", "терпила")
MORNING_QUESTION_REPLACEMENT_MARKERS = (
    "другой вопрос",
    "другой кейс",
    "можно другой",
    "давай другой",
    "дайте другой",
    "замени вопрос",
    "заменить вопрос",
    "новый вопрос",
    "не понял",
    "не поняла",
    "не понимаю",
    "не ясен",
    "неясн",
    "непонятно",
    "непонятн",
    "переформулируй",
    "поясни вопрос",
    "сложно понять",
)


async def get_or_create_morning_session(
    db: AsyncSession,
    user: User,
) -> ConversationSession:
    result = await db.execute(
        select(ConversationSession)
        .where(ConversationSession.user_id == user.id, ConversationSession.state != "closed")
        .order_by(ConversationSession.last_message_at.desc().nullslast())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if session is not None:
        session.last_message_at = now
        return session

    session = ConversationSession(
        user_id=user.id,
        source="telegram",
        state="active",
        started_at=now,
        last_message_at=now,
    )
    db.add(session)
    await db.flush()
    return session


def morning_fallback_question() -> str:
    return (
        "Представьте: вы утром открыли чат, а там короткое резкое сообщение от коллеги. "
        "Что вы напишете первым ответом, чтобы не разжечь конфликт и не проглотить раздражение молча?"
    )


def morning_question_is_valid(text: str) -> bool:
    lower = text.lower()
    return bool(text.strip()) and not any(term in lower for term in FORBIDDEN_MORNING_TERMS)


def morning_question_replacement_requested(text: str) -> bool:
    lower = text.lower().replace("ё", "е")
    return any(marker in lower for marker in MORNING_QUESTION_REPLACEMENT_MARKERS)


def compact_oracle_thoughts(summary: str) -> str:
    clean = " ".join(summary.split())
    if not clean:
        return "Ответ принят: главное здесь не идеальность, а выбранный вами первый шаг."

    sentences: list[str] = []
    start = 0
    for index, char in enumerate(clean):
        if char in ".!?":
            sentence = clean[start : index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
        if len(sentences) >= 2:
            break

    result = " ".join(sentences) if sentences else clean
    if len(result) <= 320:
        return result

    trimmed = result[:317].rsplit(" ", maxsplit=1)[0].strip()
    return f"{trimmed}..."


async def generate_morning_challenge_question() -> str:
    try:
        raw = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Придумай один простой утренний вопрос на русском для рассылки Оракула. "
                        "Его читает человек утром в телефоне: он должен сразу представить сцену "
                        "и захотеть ответить. Формат: мини-кейс из обычной жизни и один вопрос "
                        "про конкретный следующий шаг. В кейсе должны быть место или контекст, "
                        "небольшой конфликт, ограничение по времени или эмоциям и понятный выбор. "
                        "Подходящие темы: рабочий чат, семья, деньги, усталость, спор, просьба, "
                        "дедлайн, неловкий разговор, обещание, чужая ошибка. Спрашивай не про "
                        "качества человека и не про жизненные принципы, а про то, что он скажет "
                        "или сделает прямо сейчас. Хороший тон: 'Представьте: ... Что вы сделаете "
                        "первым делом?' или 'Что ответите одной фразой?'. Плохой тон: общие "
                        "вопросы вроде 'какой выбор вы сделаете сегодня?' без сцены и действия. "
                        "Пиши живым разговорным языком, без философии, без нравоучения, без Markdown. "
                        "Нельзя использовать слова 'субъект', 'объект', 'терпила'. "
                        "1-2 коротких предложения, до 230 символов."
                    ),
                },
                {"role": "user", "content": "Дай один утренний вопрос."},
            ],
            temperature=0.72,
            max_tokens=180,
        )
        question = clean_generated_text(raw)
        if morning_question_is_valid(question):
            return question
    except Exception:
        pass
    return morning_fallback_question()


async def send_morning_case_to_all_users() -> int:
    """Send the daily 10:00 morning question to every eligible Telegram user."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.lifecycle_status.in_(
                    [
                        "beginner",
                        "follower",
                        "seeker",
                        "faithful",
                        "keeper",
                        "sighted",
                        "subject",
                    ]
                ),
                User.telegram_id.is_not(None),
            )
        )
        users = result.scalars().all()
        sent_count = 0

        for user in users:
            try:
                question = await generate_morning_challenge_question()
                await send_message(
                    chat_id=int(user.telegram_id),
                    text=(
                        f"{MORNING_QUESTION_PREFIX}\n\n"
                        f"{question}\n\n"
                        "Ответьте одним сообщением. Чем честнее и точнее ответ, тем выше награда."
                    ),
                )
                session = await get_or_create_morning_session(db, user)
                session.state = "morning:wait"
                session.summary = json.dumps(
                    {"morning_question": question},
                    ensure_ascii=False,
                )
                sent_count += 1
            except Exception:
                continue

        await db.commit()
        return sent_count


async def process_morning_case_response(
    db: AsyncSession,
    user: User,
    text: str,
    question: str | None = None,
) -> tuple[str, str, int, None]:
    """Process a morning answer and award 1-5 psycoins based on quality."""
    implicit = analyze_implicit_signals(text)
    assessment, _ = await create_assessment(
        db,
        user=user,
        text=text,
        source="morning_case",
        case_prompt=question,
        implicit_signals=implicit,
        award_tokens=False,
    )

    avg_score = assessment_average_score(assessment)
    psycoins_awarded = max(1, min(5, round(avg_score / 20)))
    user.token_balance += psycoins_awarded
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    db.add(
        TokenLedgerEntry(
            user_id=user.id,
            amount=psycoins_awarded,
            reason="PsyCoin morning question",
            assessment_id=assessment.id,
        )
    )
    await db.flush()

    thoughts = compact_oracle_thoughts(assessment.summary)
    return (
        "Спасибо за ваш ответ.\n\n"
        f"Мысли Оракула: {thoughts}\n\n"
        f"Вы заработали: {psycoins(psycoins_awarded)}",
        "morning_case_assessment",
        psycoins_awarded,
        None,
    )
