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
    is_repeatable: bool
    is_owned: bool
    can_purchase: bool
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
    lifecycle_status: str
    token_balance: int
    status: str
    subjectivity_score: int
    profile_summary: str | None
    currency_icon_url: str
    closed_group_invite_url: str
    system_entry_star_price: int
    psycoin_per_star: int
    psycoin_withdraw_min: int
    star_exchange_enabled: bool
    items: list[MarketplaceItemRead]
    purchases: list[MarketplacePurchaseRead]
    inventory: list[MarketplacePurchaseRead]


class BuyRequest(BaseModel):
    telegram_id: int
    init_data: str | None = None
    item_index: int | None = None
    item_id: UUID | None = None


class BuyResponse(BaseModel):
    ok: bool
    message: str
    token_balance: int
    purchase_title: str | None = None
    purchase_item_type: str | None = None


class StarTopUpRequest(BaseModel):
    telegram_id: int
    init_data: str | None = None
    star_amount: int


class StarWithdrawalRequestCreate(BaseModel):
    telegram_id: int
    init_data: str | None = None
    token_amount: int


class StarExchangeResponse(BaseModel):
    ok: bool
    message: str
    token_balance: int
    star_amount: int | None = None
    token_amount: int | None = None
    invoice_url: str | None = None
    withdrawal_id: UUID | None = None
