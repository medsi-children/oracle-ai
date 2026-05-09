from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.case import Case
from app.schemas.assessment import AssessmentRead
from app.schemas.case import CaseAnswerCreate, CaseCreate, CaseRead
from app.schemas.user import UserCreate
from app.services.assessment import create_assessment
from app.services.users import get_or_create_user

router = APIRouter()


@router.post("", response_model=CaseRead)
async def create_case(payload: CaseCreate, db: AsyncSession = Depends(get_db)) -> Case:
    case = Case(**payload.model_dump())
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.get("", response_model=list[CaseRead])
async def list_cases(db: AsyncSession = Depends(get_db)) -> list[Case]:
    result = await db.execute(select(Case).where(Case.is_active.is_(True)).order_by(Case.created_at.desc()))
    return list(result.scalars().all())


@router.post("/answer", response_model=AssessmentRead)
async def answer_case(payload: CaseAnswerCreate, db: AsyncSession = Depends(get_db)) -> AssessmentRead:
    result = await db.execute(select(Case).where(Case.id == payload.case_id, Case.is_active.is_(True)))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    user = await get_or_create_user(db, UserCreate(telegram_id=payload.telegram_id))
    assessment, token_delta = await create_assessment(
        db,
        user=user,
        text=payload.answer,
        source="case_answer",
        case_id=case.id,
        case_prompt=case.prompt,
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
