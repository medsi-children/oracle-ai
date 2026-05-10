from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
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
