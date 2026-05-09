from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UuidPrimaryKeyMixin


class User(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128), index=True)
    first_name: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(64), default="object", nullable=False)
    subjectivity_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profile_summary: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sessions = relationship("ConversationSession", back_populates="user")
