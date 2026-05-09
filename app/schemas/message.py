from uuid import UUID

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    text: str = Field(min_length=1)
    source: str = "telegram"


class MessageResponse(BaseModel):
    user_id: UUID
    session_id: UUID
    reply: str
    mode: str = "support"
    token_delta: int = 0
    subjectivity_score: int | None = None
