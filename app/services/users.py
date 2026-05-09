from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate


async def get_or_create_user(db: AsyncSession, payload: UserCreate) -> User:
    user: User | None = None
    if payload.telegram_id is not None:
        result = await db.execute(select(User).where(User.telegram_id == payload.telegram_id))
        user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
        )
        db.add(user)
        await db.flush()
        return user

    user.username = payload.username or user.username
    user.first_name = payload.first_name or user.first_name
    await db.flush()
    return user
