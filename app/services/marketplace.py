from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketplace import MarketplaceItem, MarketplacePurchase
from app.models.user import User

SEED_ITEMS = [
    {
        "title": "Знак Искренности",
        "description": "Коллекционный символ за готовность признавать сложность и не играть роль.",
        "price_tokens": 5,
        "item_type": "collectible",
    },
    {
        "title": "Печать Спокойного Голоса",
        "description": "Плейсхолдер будущего бейджа для зрелой коммуникации в баттлах.",
        "price_tokens": 8,
        "item_type": "collectible",
    },
    {
        "title": "Фрагмент Оракула",
        "description": "Черновой collectible. Позже можно заменить на реальные награды/доступы.",
        "price_tokens": 12,
        "item_type": "collectible",
    },
]


async def ensure_marketplace_items(db: AsyncSession) -> None:
    result = await db.execute(select(MarketplaceItem).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    for item in SEED_ITEMS:
        db.add(MarketplaceItem(**item))
    await db.flush()


async def format_shop(db: AsyncSession) -> str:
    await ensure_marketplace_items(db)
    result = await db.execute(
        select(MarketplaceItem)
        .where(MarketplaceItem.is_active.is_(True))
        .order_by(MarketplaceItem.price_tokens.asc())
    )
    items = result.scalars().all()
    lines = ["Маркетплейс Оракула ИИ", "", "Пока это витрина collectibles-плейсхолдеров:"]
    for idx, item in enumerate(items, start=1):
        lines.append(f"{idx}. {item.title} — {item.price_tokens} токенов\n{item.description}")
    lines.append("\nДля покупки: /buy 1")
    return "\n\n".join(lines)


async def buy_item(db: AsyncSession, user: User, index: int) -> str:
    await ensure_marketplace_items(db)
    result = await db.execute(
        select(MarketplaceItem)
        .where(MarketplaceItem.is_active.is_(True))
        .order_by(MarketplaceItem.price_tokens.asc())
    )
    items = list(result.scalars().all())
    if index < 1 or index > len(items):
        return "Такого предмета нет. Посмотрите витрину: /shop"
    item = items[index - 1]
    if user.token_balance < item.price_tokens:
        return (
            f"Пока не хватает токенов: нужно {item.price_tokens}, у вас {user.token_balance}. "
            "Можно пройти /case и заработать еще."
        )
    user.token_balance -= item.price_tokens
    db.add(MarketplacePurchase(user_id=user.id, item_id=item.id, price_tokens=item.price_tokens))
    await db.flush()
    return f"Покупка оформлена: {item.title}. Это пока collectible-плейсхолдер."
