from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.summary import Summary


async def create_due_summaries(
    db: AsyncSession, *, older_than_minutes: int = 60
) -> list[Summary]:
    _ = (db, older_than_minutes)
    return []


async def get_unsent_summaries(db: AsyncSession) -> list[Summary]:
    _ = db
    return []


async def claim_unsent_summaries(db: AsyncSession) -> list[Summary]:
    _ = db
    return []


async def mark_summary_sent(db: AsyncSession, summary_id: UUID) -> None:
    result = await db.execute(select(Summary).where(Summary.id == summary_id))
    summary = result.scalar_one_or_none()
    if summary is None:
        return
    summary.is_sent = True
    summary.sent_at = datetime.now(UTC)
    await db.flush()
