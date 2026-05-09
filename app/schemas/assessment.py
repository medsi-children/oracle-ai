from uuid import UUID

from pydantic import BaseModel, Field


class AssessmentCreate(BaseModel):
    telegram_id: int
    source: str = "manual"
    text: str = Field(min_length=1)
    case_id: UUID | None = None
    session_id: UUID | None = None


class AssessmentRead(BaseModel):
    user_id: UUID
    assessment_id: UUID
    subjectivity: int
    honesty: int
    emotional_sovereignty: int
    cognitive_humility: int
    empathy: int
    token_delta: int
    summary: str
