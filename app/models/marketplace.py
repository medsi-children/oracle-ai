from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UuidPrimaryKeyMixin


class MarketplaceItem(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "marketplace_items"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), default="collectible", nullable=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MarketplacePurchase(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "marketplace_purchases"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    item_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("marketplace_items.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    price_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
