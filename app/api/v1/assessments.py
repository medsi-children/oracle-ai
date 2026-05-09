from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.assessment import AssessmentCreate, AssessmentRead
from app.schemas.user import UserCreate
from app.services.assessment import create_assessment
from app.services.users import get_or_create_user

router = APIRouter()


@router.post("", response_model=AssessmentRead)
async def assess_text(payload: AssessmentCreate, db: AsyncSession = Depends(get_db)) -> AssessmentRead:
    user = await get_or_create_user(db, UserCreate(telegram_id=payload.telegram_id))
    assessment, token_delta = await create_assessment(
        db,
        user=user,
        text=payload.text,
        source=payload.source,
        case_id=payload.case_id,
        session_id=payload.session_id,
    )
    await db.commit()
    return AssessmentRead(
        user_id=user.id,
        assessment_id=assessment.id,
        subjectivity=assessment.subjectivity,
        honesty=assessment.honesty,
        emotional_sovereignty=assessment.emotional_sovereignty,
        cognitive_humility=assessment.cognitive_humility,
        empathy=assessment.empathy,
        token_delta=token_delta,
        summary=assessment.summary,
    )
