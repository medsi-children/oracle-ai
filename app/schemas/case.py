from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    category: str = Field(min_length=1, max_length=128)
    difficulty: int = Field(default=1, ge=1, le=5)
    prompt: str = Field(min_length=1)


class CaseRead(BaseModel):
    id: UUID
    title: str
    category: str
    difficulty: int
    prompt: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseAnswerCreate(BaseModel):
    telegram_id: int
    case_id: UUID
    answer: str = Field(min_length=1)
