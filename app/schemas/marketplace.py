from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MarketplaceItemRead(BaseModel):
    id: UUID
    index: int
    title: str
    description: str
    price_tokens: int
    item_type: str
    image_url: str
    currency_icon_url: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MarketplacePurchaseRead(BaseModel):
    id: UUID
    item_id: UUID
    title: str
    price_tokens: int
    item_type: str
    image_url: str
    currency_icon_url: str
    created_at: datetime


class MarketplaceState(BaseModel):
    telegram_id: int
    token_balance: int
    status: str
    subjectivity_score: int
    profile_summary: str | None
    currency_icon_url: str
    items: list[MarketplaceItemRead]
    purchases: list[MarketplacePurchaseRead]


class BuyRequest(BaseModel):
    telegram_id: int
    item_index: int | None = None
    item_id: UUID | None = None


class BuyResponse(BaseModel):
    ok: bool
    message: str
    token_balance: int
