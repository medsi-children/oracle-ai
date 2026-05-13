from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.cases import get_random_case
from app.services.dialogue import format_onboarding_case, create_assessment, analyze_implicit_signals
from app.services.telegram_delivery import send_telegram_message

async def send_morning_case_to_all_users() -> int:
    """Send morning case to all eligible users at 10:00 CET.
    
    Call this endpoint daily via cron/scheduler (e.g. GitHub Actions, Render Cron, or external service).
    Text: "У Оракула есть вопрос для вас. Ответьте и получите награду в псикоинах."
    
    Scoring: 1-5 psycoins based on subjectivity quality (local + LLM assessment).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.lifecycle_status.in_(["beginner", "follower", "seeker", "faithful", "keeper", "sighted", "subject"])
            )
        )
        users = result.scalars().all()

        case = await get_random_case(db)
        sent_count = 0

        for user in users:
            try:
                text = (
                    "У Оракула есть вопрос для вас. Ответьте и получите награду в псикоинах.\n\n"
                    f"{case.prompt}\n\n"
                    "Ответьте коротко и честно — качество ответа влияет на награду (1-5 псикоинов)."
                )
                await send_telegram_message(
                    chat_id=user.telegram_id,
                    text=text,
                    reply_markup=None  # Можно добавить inline кнопку "Ответить"
                )
                sent_count += 1
            except Exception:
                continue

        return sent_count


async def process_morning_case_response(
    db: AsyncSession,
    user: User,
    text: str,
    case_id: str | None = None,
) -> tuple[str, int]:
    """Process user's morning case response and award 1-5 psycoins based on quality."""
    implicit = analyze_implicit_signals(text)
    assessment, token_delta = await create_assessment(
        db,
        user=user,
        text=text,
        source="morning_case",
        case_id=case_id,
        implicit_signals=implicit,
    )

    # Scale to 1-5 psycoins based on average score
    avg_score = (
        assessment.subjectivity + assessment.honesty + assessment.emotional_sovereignty +
        assessment.cognitive_humility + assessment.empathy
    ) / 5

    psycoins = max(1, min(5, round(avg_score / 20)))  # 1-5 range

    if psycoins > token_delta:
        # Adjust if needed
        psycoins = token_delta

    return (
        f"Спасибо за ответ!\n\n"
        f"Оценка: {avg_score:.0f}/100\n"
        f"Начислено: {psycoins} псикоинов\n\n"
        f"{assessment.summary}",
        psycoins,
    )
