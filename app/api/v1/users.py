from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserProfile, UserRead
from app.services.users import get_or_create_user

router = APIRouter()


@router.post("", response_model=UserRead)
async def upsert_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    user = await get_or_create_user(db, payload)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}/profile", response_model=UserProfile)
async def get_profile(user_id: UUID, db: AsyncSession = Depends(get_db)) -> UserProfile:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(user=user, latest_summary=user.profile_summary)
