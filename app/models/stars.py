from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UuidPrimaryKeyMixin


class StarPaymentOrder(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "star_payment_orders"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)
    star_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    token_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_payload: Mapped[str | None] = mapped_column(String(256), unique=True)
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(256), unique=True)
    note: Mapped[str | None] = mapped_column(Text)


class StarWithdrawalRequest(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "star_withdrawal_requests"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    token_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    star_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_note: Mapped[str | None] = mapped_column(Text)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
