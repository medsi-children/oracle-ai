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
    list_inventory_items,
    purchase_item,
)
from app.services.stars import (
    TelegramStarsError,
    create_star_invoice_link,
    create_withdrawal_request,
)

router = APIRouter()
DEFAULT_CLOSED_GROUP_INVITE_URL = "https://t.me/+jkSp6Vx8L35kYmRi"


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def ensure_marketplace_access(user: User) -> None:
    if user.lifecycle_status == "newbie" and not is_admin(user):
        raise HTTPException(status_code=403, detail="shop_locked_newbie")


def ensure_full_marketplace_access(user: User) -> None:
    ensure_marketplace_access(user)
    if user.lifecycle_status != "follower" and not is_admin(user):
        raise HTTPException(status_code=403, detail="shop_locked_system_entry")


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
    inventory_rows = await list_inventory_items(db, user)
    inventory = [
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
        for purchase, item in inventory_rows
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
        closed_group_invite_url=settings.closed_group_invite_url or DEFAULT_CLOSED_GROUP_INVITE_URL,
        system_entry_star_price=settings.system_entry_star_price,
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
                is_repeatable=item.is_repeatable,
                is_owned=item.is_owned,
                can_purchase=item.can_purchase,
                is_active=True,
            )
            for index, item in enumerate(items, start=1)
        ],
        purchases=purchases,
        inventory=inventory,
    )


@router.post("/buy", response_model=BuyResponse)
async def buy(payload: BuyRequest, db: AsyncSession = Depends(get_db)) -> BuyResponse:
    user = await get_user_by_telegram_id(db, payload.telegram_id)
    ensure_full_marketplace_access(user)
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
        purchase_title=item.title if ok else None,
        purchase_item_type=item.item_type if ok else None,
    )


@router.post("/stars/topup", response_model=StarExchangeResponse)
async def stars_topup(
    payload: StarTopUpRequest, db: AsyncSession = Depends(get_db)
) -> StarExchangeResponse:
    user = await get_user_by_telegram_id(db, payload.telegram_id)
    ensure_full_marketplace_access(user)
    if not settings.star_exchange_enabled:
        return StarExchangeResponse(
            ok=False,
            message="Обмен Stars временно отключен.",
            token_balance=user.token_balance,
            star_amount=payload.star_amount,
        )
    if payload.star_amount < 1 or payload.star_amount > 2500:
        return StarExchangeResponse(
            ok=False,
            message="Выберите от 1 до 2500 звезд за один обмен.",
            token_balance=user.token_balance,
            star_amount=payload.star_amount,
        )
    token_amount = payload.star_amount * settings.psycoin_per_star
    try:
        _, invoice_url = await create_star_invoice_link(
            db,
            user=user,
            order_type="psycoin_topup",
            star_amount=payload.star_amount,
            token_amount=token_amount,
            title="PsyCoin",
            description=f"{token_amount} PsyCoin за {payload.star_amount} Telegram Stars",
        )
    except TelegramStarsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await db.commit()
    return StarExchangeResponse(
        ok=True,
        message=f"Откройте счет Telegram Stars: {payload.star_amount} ⭐ = {token_amount} PsyCoin.",
        token_balance=user.token_balance,
        star_amount=payload.star_amount,
        token_amount=token_amount,
        invoice_url=invoice_url,
    )


@router.post("/stars/system-entry", response_model=StarExchangeResponse)
async def stars_system_entry(
    payload: StarTopUpRequest, db: AsyncSession = Depends(get_db)
) -> StarExchangeResponse:
    user = await get_user_by_telegram_id(db, payload.telegram_id)
    ensure_marketplace_access(user)
    if user.lifecycle_status == "follower" or is_admin(user):
        return StarExchangeResponse(
            ok=True,
            message="Вход уже открыт.",
            token_balance=user.token_balance,
            star_amount=0,
            token_amount=0,
        )
    if not settings.star_exchange_enabled:
        return StarExchangeResponse(
            ok=False,
            message="Оплата Stars временно отключена.",
            token_balance=user.token_balance,
            star_amount=settings.system_entry_star_price,
            token_amount=0,
        )
    star_amount = max(1, settings.system_entry_star_price)
    try:
        _, invoice_url = await create_star_invoice_link(
            db,
            user=user,
            order_type="system_entry",
            star_amount=star_amount,
            token_amount=0,
            title="Вход ETHOS",
            description="Доступ к закрытой системе ETHOS",
        )
    except TelegramStarsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await db.commit()
    return StarExchangeResponse(
        ok=True,
        message=f"Откройте счет Telegram Stars: вход в систему за {star_amount} ⭐.",
        token_balance=user.token_balance,
        star_amount=star_amount,
        token_amount=0,
        invoice_url=invoice_url,
    )


@router.post("/stars/withdraw", response_model=StarExchangeResponse)
async def stars_withdraw(
    payload: StarWithdrawalRequestCreate, db: AsyncSession = Depends(get_db)
) -> StarExchangeResponse:
    user = await get_user_by_telegram_id(db, payload.telegram_id)
    ensure_full_marketplace_access(user)
    if not settings.star_exchange_enabled:
        return StarExchangeResponse(
            ok=False,
            message="Вывод Stars временно отключен.",
            token_balance=user.token_balance,
        )
    try:
        request = await create_withdrawal_request(
            db,
            user=user,
            token_amount=payload.token_amount,
        )
    except TelegramStarsError as exc:
        return StarExchangeResponse(
            ok=False,
            message=str(exc),
            token_balance=user.token_balance,
        )
    await db.commit()
    return StarExchangeResponse(
        ok=True,
        message=(
            "Ваша заявка зарегистрирована.\n\n"
            f"{request.token_amount} PsyCoin зарезервированы для вывода в звезды.\n"
            f"Сумма к выплате: {request.star_amount} ⭐\n\n"
            "Администратор получил уведомление и обработает вывод вручную."
        ),
        token_balance=user.token_balance,
        star_amount=request.star_amount,
        token_amount=request.token_amount,
        withdrawal_id=request.id,
    )
