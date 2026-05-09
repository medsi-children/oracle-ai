from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.marketplace import MarketplaceItem, MarketplacePurchase
from app.models.user import User
from app.schemas.marketplace import (
    BuyRequest,
    BuyResponse,
    MarketplaceItemRead,
    MarketplacePurchaseRead,
    MarketplaceState,
)
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


@router.get("/state", response_model=MarketplaceState)
async def marketplace_state(
    telegram_id: int, db: AsyncSession = Depends(get_db)
) -> MarketplaceState:
    user = await get_user_by_telegram_id(db, telegram_id)
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
        token_balance=user.token_balance,
        status=user.status,
        subjectivity_score=user.subjectivity_score,
        profile_summary=user.profile_summary,
        currency_icon_url=PSYCOIN_ICON_URL,
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
