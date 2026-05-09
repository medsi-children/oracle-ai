from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UuidPrimaryKeyMixin


class Assessment(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "assessments"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        index=True,
    )
    case_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    subjectivity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    honesty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emotional_sovereignty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cognitive_humility: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    empathy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
