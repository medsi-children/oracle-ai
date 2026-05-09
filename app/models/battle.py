from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UuidPrimaryKeyMixin


class Battle(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "battles"

    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    case_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[str | None] = mapped_column(Text)


class BattleParticipant(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "battle_participants"

    battle_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("battles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    side: Mapped[str | None] = mapped_column(String(64))
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
