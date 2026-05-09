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
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MarketplacePurchaseRead(BaseModel):
    id: UUID
    item_id: UUID
    title: str
    price_tokens: int
    created_at: datetime


class MarketplaceState(BaseModel):
    telegram_id: int
    token_balance: int
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
