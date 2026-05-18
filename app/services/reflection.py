from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.message import Message
from app.models.session import ConversationSession
from app.models.user import User
from app.services.llm import clean_generated_text, extract_json_object, openrouter_chat


@dataclass(frozen=True)
class ReflectionResult:
    should_reflect: bool
    message: str = ""
    reason: str = ""


async def build_user_pattern_context(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession | None = None,
    assessment_limit: int = 6,
    message_limit: int = 8,
) -> str:
    assessment_result = await db.execute(
        select(Assessment)
        .where(Assessment.user_id == user.id)
        .order_by(Assessment.created_at.desc())
        .limit(assessment_limit)
    )
    assessments = list(reversed(assessment_result.scalars().all()))
    assessment_lines = [
        (
            f"{assessment.source}: субъектность {assessment.subjectivity}/100, "
            f"честность {assessment.honesty}/100, контроль реакции "
            f"{assessment.emotional_sovereignty}/100, проверка реальности "
            f"{assessment.cognitive_humility}/100, эмпатия {assessment.empathy}/100. "
            f"Вывод: {assessment.summary}"
        )
        for assessment in assessments
    ]

    message_result = await db.execute(
        select(Message)
        .where(Message.user_id == user.id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(message_limit + 8)
    )
    recent_texts: list[str] = []
    for message in message_result.scalars().all():
        if message.message_metadata.get("callback_data"):
            continue
        text = message.content.strip()
        if not text or text.startswith("/"):
            continue
        recent_texts.append(text)
        if len(recent_texts) >= message_limit:
            break

    return (
        f"Текущий профиль: {user.profile_summary or 'Профиль еще формируется.'}\n\n"
        f"Последние оценки:\n{chr(10).join(assessment_lines) or 'Оценок пока нет.'}\n\n"
        f"Последние ответы пользователя:\n{chr(10).join(reversed(recent_texts)) or 'Ответов пока нет.'}"
    )


def local_reflection_from_signals(text: str, implicit: dict) -> ReflectionResult:
    word_count = int(implicit.get("word_count") or 0)
    if implicit.get("aggression_markers"):
        return ReflectionResult(
            True,
            "В ответе есть энергия, но она уходит в атаку. Так внимание смещается с решения на реакцию.",
            "aggression",
        )
    if implicit.get("appeasement_markers"):
        return ReflectionResult(
            True,
            "Ответ звучит так, будто ты ищешь одобрения, а не формулируешь свою позицию. Сильная позиция выдерживает уточнение и спор.",
            "appeasement",
        )
    if float(implicit.get("cliche_density") or 0) >= 0.18:
        return ReflectionResult(
            True,
            "Ответ звучит правильно, но слишком общо. В нем не видно, что ты готов сделать на практике и с какими последствиями готов иметь дело.",
            "cliche",
        )
    if word_count < 10:
        return ReflectionResult(
            True,
            "Ответ слишком короткий для выбора с последствиями. Сейчас видна позиция, но не видно действия и следующего шага.",
            "too_short",
        )
    if implicit.get("latency_bucket") == "impulsive":
        return ReflectionResult(
            True,
            "Ответ пришел очень быстро. Возможно, это первая реакция, а не выбранная позиция.",
            "impulsive",
        )
    if not implicit.get("uses_first_person") and word_count >= 18:
        return ReflectionResult(
            True,
            "В ответе много общего рассуждения, но мало твоего личного выбора. Здесь важна не правильная фраза, а твой реальный шаг.",
            "no_first_person",
        )
    return ReflectionResult(False)


async def build_response_reflection(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession,
    activity_type: str,
    prompt: str,
    answer: str,
    implicit: dict,
) -> ReflectionResult:
    local = local_reflection_from_signals(answer, implicit)
    if local.should_reflect:
        return local

    context = await build_user_pattern_context(db, user=user, session=session)
    try:
        raw_text = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — Оракул ETHOS. Реши, стоит ли перед фиксацией ответа показать "
                        "короткое зеркало пользователю. Срабатывай только если есть явный "
                        "разрыв с предыдущими ответами, уход от конкретного действия и последствий, смена принципа "
                        "без признания, общие слова вместо действия или потеря влияния на ситуацию. "
                        "Не учи, как отвечать правильно. Не раскрывай критерии. Не используй "
                        "туманные формулировки, пафос и markdown. Верни только JSON: "
                        '{"should_reflect":true/false,"reason":"short","message":"1-2 коротких предложения"}.'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Тип сценария: {activity_type}\n"
                        f"Кейс/тема:\n{prompt}\n\n"
                        f"Ответ:\n{answer}\n\n"
                        f"Скрытые сигналы:\n{implicit}\n\n"
                        f"История и профиль:\n{context}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=260,
        )
        raw = extract_json_object(raw_text)
        should_reflect = bool(raw.get("should_reflect"))
        message = clean_generated_text(str(raw.get("message") or ""))
        reason = str(raw.get("reason") or "")
        if should_reflect and message:
            return ReflectionResult(True, message, reason)
    except Exception:
        pass
    return ReflectionResult(False)
