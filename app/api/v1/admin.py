from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.admins import is_admin
from app.services.summaries import claim_unsent_summaries, mark_summary_sent

router = APIRouter()


class SummaryOut(BaseModel):
    id: UUID
    text: str
    username: str | None = None
    chat_id: int | None = None


class DueSummariesOut(BaseModel):
    generated_at: datetime
    summaries: list[SummaryOut]


@router.get("/due-summaries", response_model=DueSummariesOut)
async def due_summaries(db: AsyncSession = Depends(get_db)) -> DueSummariesOut:
    summaries = await claim_unsent_summaries(db)
    await db.commit()
    return DueSummariesOut(
        generated_at=datetime.now(UTC),
        summaries=[
            SummaryOut(id=s.id, text=s.text, username=s.username, chat_id=s.chat_id) for s in summaries
        ],
    )


@router.post("/summaries/{summary_id}/sent")
async def summary_sent(summary_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await mark_summary_sent(db, summary_id)
    await db.commit()
    return {"status": "ok"}


# ==================== ADMIN PANEL ENDPOINTS ====================

class AdminActionRequest(BaseModel):
    admin_telegram_id: int
    target_telegram_id: int


class GrantCoinsRequest(AdminActionRequest):
    amount: int = Field(..., gt=0, le=10000)


class SetScoreRequest(AdminActionRequest):
    score: int = Field(..., ge=0, le=100)


class SetStatusRequest(AdminActionRequest):
    status: str = Field(..., pattern="^(object|seeker|faithful|keeper|sighted|subject)$")


class SetLifecycleRequest(AdminActionRequest):
    lifecycle: str = Field(..., pattern="^(newbie|beginner|follower|admin)$")


class ResetUserRequest(AdminActionRequest):
    pass


async def verify_admin(admin_telegram_id: int, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.telegram_id == admin_telegram_id))
    admin = result.scalar_one_or_none()
    if not admin or not is_admin(admin):
        raise HTTPException(status_code=403, detail="Access denied")
    return admin


@router.post("/admin/grant-coins")
async def grant_coins(request: GrantCoinsRequest, db: AsyncSession = Depends(get_db)):
    await verify_admin(request.admin_telegram_id, db)

    result = await db.execute(select(User).where(User.telegram_id == request.target_telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.token_balance += request.amount
    await db.commit()

    return {
        "status": "ok",
        "message": f"Начислено {request.amount} псикоинов пользователю @{user.username or user.telegram_id}",
        "new_balance": user.token_balance,
    }


@router.post("/admin/set-score")
async def set_score(request: SetScoreRequest, db: AsyncSession = Depends(get_db)):
    await verify_admin(request.admin_telegram_id, db)

    result = await db.execute(select(User).where(User.telegram_id == request.target_telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.subjectivity_score = request.score
    await db.commit()

    return {
        "status": "ok",
        "message": f"Индекс субъектности установлен: {request.score}/100",
    }


@router.post("/admin/set-status")
async def set_status(request: SetStatusRequest, db: AsyncSession = Depends(get_db)):
    await verify_admin(request.admin_telegram_id, db)

    result = await db.execute(select(User).where(User.telegram_id == request.target_telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = request.status
    await db.commit()

    return {
        "status": "ok",
        "message": f"Статус изменён на: {request.status}",
    }


@router.post("/admin/set-lifecycle")
async def set_lifecycle(request: SetLifecycleRequest, db: AsyncSession = Depends(get_db)):
    await verify_admin(request.admin_telegram_id, db)

    result = await db.execute(select(User).where(User.telegram_id == request.target_telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.lifecycle_status = request.lifecycle
    await db.commit()

    return {
        "status": "ok",
        "message": f"Этап доступа изменён на: {request.lifecycle}",
    }


@router.post("/admin/reset-user")
async def reset_user(request: ResetUserRequest, db: AsyncSession = Depends(get_db)):
    await verify_admin(request.admin_telegram_id, db)

    result = await db.execute(select(User).where(User.telegram_id == request.target_telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.token_balance = 0
    user.subjectivity_score = 0
    user.status = "object"
    user.lifecycle_status = "newbie"
    user.profile_summary = None
    await db.commit()

    return {
        "status": "ok",
        "message": "Пользователь полностью сброшен",
    }


@router.get("/admin/users")
async def list_users(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit)
    )
    users = result.scalars().all()

    return {
        "users": [
            {
                "telegram_id": u.telegram_id,
                "username": u.username,
                "status": u.status,
                "lifecycle": u.lifecycle_status,
                "score": u.subjectivity_score,
                "balance": u.token_balance,
            }
            for u in users
        ]
    }
