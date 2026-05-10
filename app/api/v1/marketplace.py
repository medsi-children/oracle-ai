from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.marketplace import MarketplaceItem, MarketplacePurchase
from app.models.user import User
from app.schemas.marketplace import (
    BuyRequest,
    BuyResponse,
    MarketplaceItemRead,
    MarketplacePurchaseRead,
    MarketplaceState,
    StarExchangeResponse,
    StarTopUpRequest,
    StarWithdrawalRequestCreate,
)
from app.services.admins import is_admin
from app.services.llm import clean_generated_text
from app.services.marketplace import (
    PSYCOIN_ICON_URL,
    get_item_image_url,
    list_active_items,
    purchase_item,
)

router = APIRouter()


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def ensure_marketplace_access(user: User) -> None:
    if user.lifecycle_status == "newbie" and not is_admin(user):
        raise HTTPException(status_code=403, detail="shop_locked_newbie")


@router.get("/state", response_model=MarketplaceState)
async def marketplace_state(
    telegram_id: int, db: AsyncSession = Depends(get_db)
) -> MarketplaceState:
    user = await get_user_by_telegram_id(db, telegram_id)
    ensure_marketplace_access(user)
    items = await list_active_items(db, user)
    purchases_result = await db.execute(
        select(MarketplacePurchase, MarketplaceItem)
        .join(MarketplaceItem, MarketplaceItem.id == MarketplacePurchase.item_id)
        .where(MarketplacePurchase.user_id == user.id)
        .order_by(MarketplacePurchase.created_at.desc())
    )
    purchases = [
        MarketplacePurchaseRead(
            id=purchase.id,
            item_id=item.id,
            title=item.title,
            price_tokens=purchase.price_tokens,
            item_type=item.item_type,
            image_url=get_item_image_url(item),
            currency_icon_url=PSYCOIN_ICON_URL,
            created_at=purchase.created_at,
        )
        for purchase, item in purchases_result.all()
    ]
    return MarketplaceState(
        telegram_id=telegram_id,
        lifecycle_status=user.lifecycle_status,
        token_balance=user.token_balance,
        status=user.status,
        subjectivity_score=user.subjectivity_score,
        profile_summary=(
            clean_generated_text(user.profile_summary) if user.profile_summary else None
        ),
        currency_icon_url=PSYCOIN_ICON_URL,
        psycoin_per_star=settings.psycoin_per_star,
        psycoin_withdraw_min=settings.psycoin_withdraw_min,
        star_exchange_enabled=settings.star_exchange_enabled,
        items=[
            MarketplaceItemRead(
                id=item.item.id,
                index=index,
                title=item.title,
                description=item.description,
                price_tokens=item.price_tokens,
                item_type=item.item_type,
                image_url=item.image_url,
                currency_icon_url=PSYCOIN_ICON_URL,
                is_active=True,
            )
            for index, item in enumerate(items, start=1)
        ],
        purchases=purchases,
    )


@router.post("/buy", response_model=BuyResponse)
async def buy(payload: BuyRequest, db: AsyncSession = Depends(get_db)) -> BuyResponse:
    user = await get_user_by_telegram_id(db, payload.telegram_id)
    ensure_marketplace_access(user)
    items = await list_active_items(db, user)
    item = None
    if payload.item_id is not None:
        item = next(
            (candidate for candidate in items if candidate.item.id == payload.item_id),
            None,
        )
    elif payload.item_index is not None and 1 <= payload.item_index <= len(items):
        item = items[payload.item_index - 1]

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    ok, message = await purchase_item(db, user, item)
    await db.commit()
    return BuyResponse(
        ok=ok,
        message=message,
        token_balance=user.token_balance,
    )


@router.post("/stars/topup", response_model=StarExchangeResponse)
async def stars_topup(
    payload: StarTopUpRequest, db: AsyncSession = Depends(get_db)
) -> StarExchangeResponse:
    user = await get_user_by_telegram_id(db, payload.telegram_id)
    ensure_marketplace_access(user)
    return StarExchangeResponse(
        ok=False,
        message="В разработке...",
        token_balance=user.token_balance,
        star_amount=payload.star_amount,
    )


@router.post("/stars/withdraw", response_model=StarExchangeResponse)
async def stars_withdraw(
    payload: StarWithdrawalRequestCreate, db: AsyncSession = Depends(get_db)
) -> StarExchangeResponse:
    user = await get_user_by_telegram_id(db, payload.telegram_id)
    ensure_marketplace_access(user)
    star_amount = payload.token_amount // max(1, settings.psycoin_per_star)
    return StarExchangeResponse(
        ok=False,
        message="В разработке...",
        token_balance=user.token_balance,
        star_amount=star_amount,
    )
