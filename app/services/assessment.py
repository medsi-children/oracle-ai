import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.llm import (
    ASSESSMENT_SYSTEM_PROMPT,
    clean_generated_text,
    extract_json_object,
    openrouter_chat,
)


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


CLICHE_MARKERS = [
    "все не так однозначно",
    "надо быть добрее",
    "каждый имеет право",
    "главное оставаться человеком",
    "истина где-то посередине",
    "я вне политики",
    "просто выполнял",
    "так принято",
    "ничего личного",
    "я хороший человек",
    "как все нормальные люди",
]

APPEASEMENT_MARKERS = [
    "ты мудрый",
    "о великий",
    "оракул прав",
    "полностью согласен с тобой",
    "как скажешь",
]

AGGRESSION_MARKERS = [
    "ненавижу",
    "раздавить",
    "уничтожить",
    "заткнись",
    "твари",
]


def clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


def calculate_psycoin_award(score_100: int) -> int:
    score_10 = score_100 / 10
    if score_10 < 5:
        return 0
    if score_10 >= 9:
        return 7
    return max(1, min(5, round(score_10 - 4)))


def analyze_implicit_signals(text: str, *, latency_seconds: float | None = None) -> dict:
    lower = text.lower()
    words = re.findall(r"[\w-]+", lower, flags=re.UNICODE)
    matched_cliches = [marker for marker in CLICHE_MARKERS if marker in lower]
    matched_appeasement = [marker for marker in APPEASEMENT_MARKERS if marker in lower]
    matched_aggression = [marker for marker in AGGRESSION_MARKERS if marker in lower]
    cliche_density = round(min(1.0, len(matched_cliches) / max(1, len(words) / 12)), 2)

    latency_bucket = "unknown"
    hesitation_score: int | None = None
    if latency_seconds is not None:
        if latency_seconds < 8:
            latency_bucket = "impulsive"
            hesitation_score = 35
        elif latency_seconds <= 180:
            latency_bucket = "steady"
            hesitation_score = 78
        elif latency_seconds <= 420:
            latency_bucket = "constructed"
            hesitation_score = 58
        else:
            latency_bucket = "overconstructed"
            hesitation_score = 42

    return {
        "latency_seconds": round(latency_seconds, 3) if latency_seconds is not None else None,
        "latency_bucket": latency_bucket,
        "hesitation_score": hesitation_score,
        "word_count": len(words),
        "cliche_density": cliche_density,
        "matched_cliches": matched_cliches,
        "appeasement_markers": matched_appeasement,
        "aggression_markers": matched_aggression,
        "uses_first_person": any(word in {"я", "мне", "меня", "мой", "моя"} for word in words),
    }


@dataclass(frozen=True)
class AssessmentResult:
    subjectivity: int
    honesty: int
    emotional_sovereignty: int
    cognitive_humility: int
    empathy: int
    integrity: int
    awareness: int
    courage: int
    token_delta: int
    summary: str
    next_probe: str
    raw: dict


def score_text_locally(text: str, *, implicit_signals: dict | None = None) -> AssessmentResult:
    """Temporary deterministic scorer until we connect a real LLM assessment."""
    implicit = implicit_signals or analyze_implicit_signals(text)
    words = [w for w in text.strip().split() if w]
    length_score = min(30, len(words) * 2)
    has_self_reflection = any(
        marker in text.lower()
        for marker in ["я думаю", "я чувствую", "мне кажется", "ошиб", "сомнева"]
    )
    has_other_view = any(
        marker in text.lower()
        for marker in ["с другой стороны", "возможно", "может быть", "понимаю"]
    )
    cliche_penalty = round(float(implicit.get("cliche_density") or 0) * 20)
    latency_bucket = implicit.get("latency_bucket")
    latency_adjustment = (
        4
        if latency_bucket == "steady"
        else -5
        if latency_bucket == "impulsive"
        else -3
        if latency_bucket in {"constructed", "overconstructed"}
        else 0
    )

    subjectivity = clamp(
        35 + length_score + (15 if has_self_reflection else 0) - cliche_penalty + latency_adjustment
    )
    honesty = clamp(40 + (20 if has_self_reflection else 0) + min(20, len(words)) - cliche_penalty)
    emotional_sovereignty = clamp(
        35 + (20 if has_other_view else 0) + min(25, len(words)) + latency_adjustment
    )
    cognitive_humility = clamp(
        30
        + (25 if has_other_view else 0)
        + (15 if "не знаю" in text.lower() else 0)
        - cliche_penalty
    )
    empathy = clamp(
        35 + (20 if any(m in text.lower() for m in ["друг", "человек", "люд", "понимаю"]) else 0)
    )
    avg = round((subjectivity + honesty + emotional_sovereignty + cognitive_humility + empathy) / 5)
    token_delta = calculate_psycoin_award(avg)
    integrity = clamp(round((honesty + subjectivity) / 20), 0, 10)
    awareness = clamp(round((cognitive_humility + empathy) / 20), 0, 10)
    courage = clamp(round((emotional_sovereignty + honesty) / 20), 0, 10)

    return AssessmentResult(
        subjectivity=subjectivity,
        honesty=honesty,
        emotional_sovereignty=emotional_sovereignty,
        cognitive_humility=cognitive_humility,
        empathy=empathy,
        integrity=integrity,
        awareness=awareness,
        courage=courage,
        token_delta=token_delta,
        summary=(
            "Предварительная локальная оценка: ответ сохранен, видны базовые признаки "
            "рефлексии. Оракул отметил не только смысл ответа, но и его форму."
        ),
        next_probe="Что в этом ответе было твоим настоящим мотивом, а не красивой формулировкой?",
        raw={"word_count": len(words), "implicit": implicit, "local_scorer": True},
    )


async def score_text_with_oracle(
    text: str,
    *,
    case_prompt: str | None = None,
    implicit_signals: dict | None = None,
) -> AssessmentResult:
    content_parts = []
    if case_prompt is not None:
        content_parts.append(f"Кейс:\n{case_prompt}")
    content_parts.append(f"Ответ пользователя:\n{text}")
    if implicit_signals:
        content_parts.append(f"Скрытые метаданные для оценки:\n{implicit_signals}")
    content = "\n\n".join(content_parts)
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
        integrity = int(raw.get("integrity", 0))
        awareness = int(raw.get("awareness", 0))
        courage = int(raw.get("courage", 0))
        avg = round(
            (subjectivity + honesty + emotional_sovereignty + cognitive_humility + empathy) / 5
        )
        ethos_avg = round(((integrity + awareness + courage) / 3) * 10)
        token_delta = calculate_psycoin_award(round((avg * 0.7) + (ethos_avg * 0.3)))
        summary = clean_generated_text(str(raw.get("summary") or "Ответ оценен Оракулом ИИ."))
        growth_hint = raw.get("growth_hint")
        if growth_hint:
            clean_hint = clean_generated_text(str(growth_hint))
            summary = f"{summary}\n\nЗона роста: {clean_hint}"
        next_probe = clean_generated_text(str(raw.get("next_probe") or "")).strip()
        return AssessmentResult(
            subjectivity=subjectivity,
            honesty=honesty,
            emotional_sovereignty=emotional_sovereignty,
            cognitive_humility=cognitive_humility,
            empathy=empathy,
            integrity=integrity,
            awareness=awareness,
            courage=courage,
            token_delta=token_delta,
            summary=summary,
            next_probe=next_probe,
            raw={"oracle": raw, "implicit": implicit_signals or {}, "local_scorer": False},
        )
    except Exception as error:
        fallback = score_text_locally(text, implicit_signals=implicit_signals)
        return AssessmentResult(
            **{
                **fallback.__dict__,
                "summary": fallback.summary
                + "\n\nИИ-оценка временно недоступна, использована локальная оценка.",
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
    implicit_signals: dict | None = None,
    use_llm: bool = True,
    award_tokens: bool = True,
) -> tuple[Assessment, int]:
    result = (
        await score_text_with_oracle(
            text, case_prompt=case_prompt, implicit_signals=implicit_signals
        )
        if use_llm
        else score_text_locally(text, implicit_signals=implicit_signals)
    )
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

    previous_score = user.subjectivity_score
    base_delta = result.token_delta if award_tokens else 0
    if base_delta:
        db.add(
            TokenLedgerEntry(
                user_id=user.id,
                amount=base_delta,
                reason=f"PsyCoin assessment: {source}",
                assessment_id=assessment.id,
            )
        )

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
    improvement_bonus = 0
    if award_tokens and previous_score > 0 and next_score - previous_score >= 8:
        improvement_bonus = 1
        db.add(
            TokenLedgerEntry(
                user_id=user.id,
                amount=improvement_bonus,
                reason=f"PsyCoin improvement bonus: {source}",
                assessment_id=assessment.id,
            )
        )

    token_delta = base_delta + improvement_bonus
    if token_delta:
        user.token_balance += token_delta

    if source == "support_signal":
        user.subjectivity_score = round((user.subjectivity_score * 0.8) + (next_score * 0.2))
    else:
        user.subjectivity_score = next_score
        user.profile_summary = result.summary
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    await db.flush()
    return assessment, token_delta
