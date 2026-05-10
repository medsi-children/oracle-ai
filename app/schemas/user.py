from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    telegram_id: int | None = None
    username: str | None = None
    first_name: str | None = None


class UserRead(BaseModel):
    id: UUID
    telegram_id: int | None
    username: str | None
    first_name: str | None
    lifecycle_status: str
    status: str
    subjectivity_score: int
    token_balance: int
    profile_summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfile(BaseModel):
    user: UserRead
    latest_summary: str | None = None
