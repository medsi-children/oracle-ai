from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.llm import ASSESSMENT_SYSTEM_PROMPT, extract_json_object, openrouter_chat


def calculate_status(score: int, token_balance: int) -> str:
    if score >= 85 and token_balance >= 80:
        return "subject"
    if score >= 75 and token_balance >= 45:
        return "sighted"
    if score >= 65 and token_balance >= 25:
        return "keeper"
    if score >= 55 and token_balance >= 10:
        return "faithful"
    if score >= 40 or token_balance >= 3:
        return "seeker"
    return "object"


@dataclass(frozen=True)
class AssessmentResult:
    subjectivity: int
    honesty: int
    emotional_sovereignty: int
    cognitive_humility: int
    empathy: int
    token_delta: int
    summary: str
    raw: dict


def score_text_locally(text: str) -> AssessmentResult:
    """Temporary deterministic scorer until we connect a real LLM assessment."""
    words = [w for w in text.strip().split() if w]
    length_score = min(30, len(words) * 2)
    has_self_reflection = any(marker in text.lower() for marker in ["я думаю", "я чувствую", "мне кажется", "ошиб", "сомнева"])
    has_other_view = any(marker in text.lower() for marker in ["с другой стороны", "возможно", "может быть", "понимаю"])

    subjectivity = min(100, 35 + length_score + (15 if has_self_reflection else 0))
    honesty = min(100, 40 + (20 if has_self_reflection else 0) + min(20, len(words)))
    emotional_sovereignty = min(100, 35 + (20 if has_other_view else 0) + min(25, len(words)))
    cognitive_humility = min(100, 30 + (25 if has_other_view else 0) + (15 if "не знаю" in text.lower() else 0))
    empathy = min(100, 35 + (20 if any(m in text.lower() for m in ["друг", "человек", "люд", "понимаю"]) else 0))
    avg = round((subjectivity + honesty + emotional_sovereignty + cognitive_humility + empathy) / 5)
    token_delta = max(0, round(avg / 20))

    return AssessmentResult(
        subjectivity=subjectivity,
        honesty=honesty,
        emotional_sovereignty=emotional_sovereignty,
        cognitive_humility=cognitive_humility,
        empathy=empathy,
        token_delta=token_delta,
        summary=(
            "Предварительная локальная оценка: ответ сохранен, видны базовые признаки "
            "рефлексии. Позже этот блок будет заменен оценкой ИИ-Оракула."
        ),
        raw={"word_count": len(words), "local_scorer": True},
    )


async def score_text_with_oracle(text: str, *, case_prompt: str | None = None) -> AssessmentResult:
    content = text if case_prompt is None else f"Кейс:\n{case_prompt}\n\nОтвет пользователя:\n{text}"
    try:
        raw_text = await openrouter_chat(
            [
                {"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
            max_tokens=650,
        )
        raw = extract_json_object(raw_text)
        subjectivity = int(raw.get("subjectivity", 0))
        honesty = int(raw.get("honesty", 0))
        emotional_sovereignty = int(raw.get("emotional_sovereignty", 0))
        cognitive_humility = int(raw.get("cognitive_humility", 0))
        empathy = int(raw.get("empathy", 0))
        avg = round(
            (
                subjectivity
                + honesty
                + emotional_sovereignty
                + cognitive_humility
                + empathy
            )
            / 5
        )
        token_delta = max(0, min(7, round(avg / 18)))
        summary = str(raw.get("summary") or "Ответ оценен Оракулом ИИ.")
        growth_hint = raw.get("growth_hint")
        if growth_hint:
            summary = f"{summary}\n\nЗона роста: {growth_hint}"
        return AssessmentResult(
            subjectivity=subjectivity,
            honesty=honesty,
            emotional_sovereignty=emotional_sovereignty,
            cognitive_humility=cognitive_humility,
            empathy=empathy,
            token_delta=token_delta,
            summary=summary,
            raw={"oracle": raw, "local_scorer": False},
        )
    except Exception as error:
        fallback = score_text_locally(text)
        return AssessmentResult(
            **{
                **fallback.__dict__,
                "summary": fallback.summary
                + f"\n\nИИ-оценка временно недоступна, использована локальная оценка.",
                "raw": {**fallback.raw, "llm_error": str(error)},
            }
        )


async def create_assessment(
    db: AsyncSession,
    *,
    user: User,
    text: str,
    source: str,
    case_id=None,
    session_id=None,
    case_prompt: str | None = None,
    use_llm: bool = True,
    award_tokens: bool = True,
) -> tuple[Assessment, int]:
    result = await score_text_with_oracle(text, case_prompt=case_prompt) if use_llm else score_text_locally(text)
    assessment = Assessment(
        user_id=user.id,
        session_id=session_id,
        case_id=case_id,
        source=source,
        subjectivity=result.subjectivity,
        honesty=result.honesty,
        emotional_sovereignty=result.emotional_sovereignty,
        cognitive_humility=result.cognitive_humility,
        empathy=result.empathy,
        summary=result.summary,
        raw=result.raw,
    )
    db.add(assessment)
    await db.flush()

    token_delta = result.token_delta if award_tokens else 0
    if token_delta:
        db.add(
            TokenLedgerEntry(
                user_id=user.id,
                amount=token_delta,
                reason=f"Assessment: {source}",
                assessment_id=assessment.id,
            )
        )
        user.token_balance += token_delta

    next_score = round(
        (
            result.subjectivity
            + result.honesty
            + result.emotional_sovereignty
            + result.cognitive_humility
            + result.empathy
        )
        / 5
    )
    if source == "support_signal":
        user.subjectivity_score = round((user.subjectivity_score * 0.8) + (next_score * 0.2))
    else:
        user.subjectivity_score = next_score
        user.profile_summary = result.summary
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    await db.flush()
    return assessment, token_delta
