from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketplace import MarketplaceItem, MarketplacePurchase
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.llm import clean_generated_text, openrouter_chat

PSYCOIN_ICON_URL = "/static/shop/psycoin.png"
WISDOM_SPHERE_PRICES = [20, 40, 80, 150, 300, 600, 999]


def collectible_asset(slug: str) -> str:
    return f"/static/shop/items/{slug}.png"


SEED_ITEMS = [
    {
        "title": "✨ Искра Осознания",
        "description": (
            "Повышает осознанность владельца на 10%.\n"
            "Награда за момент первого осознания, что жизнь убегает сквозь пальцы, "
            "за готовность искать абсолютную истину и признавать свои ошибки."
        ),
        "price_tokens": 10,
        "item_type": "collectible",
        "asset_slug": "spark-awareness",
    },
    {
        "title": "🔥 Пламя Безмятежности",
        "description": (
            "Магический огонь, увеличивающий невозмутимость в психологических баттлах на 20%.\n"
            "Награда за власть над своей реакцией, сохранение достоинства в стрессе."
        ),
        "price_tokens": 35,
        "item_type": "collectible",
        "asset_slug": "flame-serenity",
    },
    {
        "title": "🪞 Зеркало Искренности",
        "legacy_title": "Знак Искренности",
        "description": (
            "Волшебное зеркало, в котором виднеется ваше настоящее я.\n"
            "Награда за стремление к отсутствию масок и признание всех своих сторон, "
            "включая темные."
        ),
        "price_tokens": 90,
        "item_type": "collectible",
        "asset_slug": "mirror-sincerity",
    },
    {
        "title": "💍 Серебряный Перстень",
        "description": (
            "Увеличивает мудрость владельца на 40%.\n"
            "Награда за осознанный выбор своего пути, стремление к правде и сопротивление лжи."
        ),
        "price_tokens": 220,
        "item_type": "collectible",
        "asset_slug": "silver-ring",
    },
    {
        "title": "🦊 Золотой Лис",
        "description": (
            "Статуэтка лиса, увеличивающая эмпатию на 30%.\n"
            "Награда за сострадание через действие, а не через слова."
        ),
        "price_tokens": 540,
        "item_type": "collectible",
        "asset_slug": "golden-fox",
    },
    {
        "title": "💎 Бриллиантовое Сердце",
        "description": (
            "Делает своего владельца абсолютно прозрачным.\n"
            "Награда за честность, открытость, преданность принципам "
            "и отсутствие двойных стандартов."
        ),
        "price_tokens": 999,
        "item_type": "collectible",
        "asset_slug": "diamond-heart",
    },
    {
        "title": "👑 Премиум",
        "description": (
            "Открывает право задавать собственную тему баттла и дает доступ "
            "к привилегии внутри системы ETHOS."
        ),
        "price_tokens": 120,
        "item_type": "privilege_custom_battle_topic",
        "asset_slug": "custom-battle-topic",
    },
    {
        "title": "🔮 Сфера Мудрости",
        "description": (
            "Живая сфера самопознания. После открытия Оракул присылает личную "
            "рекомендацию на основе тестирования и наблюдения."
        ),
        "price_tokens": 20,
        "item_type": "wisdom_sphere",
        "asset_slug": "wisdom-sphere",
    },
]


@dataclass
class StorefrontItem:
    item: MarketplaceItem
    title: str
    description: str
    price_tokens: int
    item_type: str
    image_url: str
    currency_icon_url: str = PSYCOIN_ICON_URL


async def ensure_marketplace_items(db: AsyncSession) -> None:
    result = await db.execute(select(MarketplaceItem))
    existing = list(result.scalars().all())
    by_title = {item.title: item for item in existing}
    known_titles = {seed_item["title"] for seed_item in SEED_ITEMS} | {
        seed_item["legacy_title"] for seed_item in SEED_ITEMS if seed_item.get("legacy_title")
    }

    for existing_item in existing:
        if existing_item.title not in known_titles:
            existing_item.is_active = False

    for seed_item in SEED_ITEMS:
        data = {
            key: value
            for key, value in seed_item.items()
            if key not in {"legacy_title", "asset_slug"}
        }
        candidate = by_title.get(seed_item["title"])
        legacy_title = seed_item.get("legacy_title")
        if candidate is None and legacy_title:
            candidate = by_title.get(legacy_title)
        if candidate is None:
            db.add(MarketplaceItem(**data))
            continue
        candidate.title = data["title"]
        candidate.description = data["description"]
        candidate.price_tokens = data["price_tokens"]
        candidate.item_type = data["item_type"]
        candidate.is_active = True
    await db.flush()


def get_seed_item(item: MarketplaceItem) -> dict | None:
    for seed_item in SEED_ITEMS:
        if seed_item["title"] == item.title:
            return seed_item
        if seed_item.get("legacy_title") == item.title:
            return seed_item
    return None


def get_item_image_url(item: MarketplaceItem) -> str:
    if item.item_type.startswith("recommendation_") or item.item_type == "wisdom_sphere":
        return collectible_asset("wisdom-sphere")
    seed_item = get_seed_item(item)
    slug = str(seed_item.get("asset_slug")) if seed_item else "item"
    return collectible_asset(slug)


async def get_wisdom_sphere_unlock_count(db: AsyncSession, user: User) -> int:
    result = await db.execute(
        select(MarketplacePurchase, MarketplaceItem)
        .join(MarketplaceItem, MarketplaceItem.id == MarketplacePurchase.item_id)
        .where(
            MarketplacePurchase.user_id == user.id,
            MarketplaceItem.item_type.in_(
                {
                    "wisdom_sphere",
                    "recommendation_reaction_focus",
                    "recommendation_honesty",
                    "recommendation_boundaries",
                    "recommendation_emotional_sovereignty",
                    "recommendation_cognitive_clarity",
                    "recommendation_active_intelligence",
                }
            ),
        )
    )
    return len(result.all())


def build_wisdom_sphere_description(level: int) -> str:
    tier = level + 1
    return (
        f"Ступень {tier} из {len(WISDOM_SPHERE_PRICES)}.\n"
        "Кнопка «Узнать о себе» открывает личное послание Оракула.\n"
        "Чем выше ступень, тем глубже, длиннее и ценнее рекомендация."
    )


async def build_storefront_items(db: AsyncSession, user: User) -> list[StorefrontItem]:
    await ensure_marketplace_items(db)
    result = await db.execute(
        select(MarketplaceItem)
        .where(MarketplaceItem.is_active.is_(True))
        .order_by(MarketplaceItem.price_tokens.asc(), MarketplaceItem.created_at.asc())
    )
    items = list(result.scalars().all())
    unlock_count = await get_wisdom_sphere_unlock_count(db, user)

    storefront: list[StorefrontItem] = []
    for item in items:
        if item.item_type.startswith("recommendation_"):
            continue
        if item.item_type == "wisdom_sphere":
            if unlock_count >= len(WISDOM_SPHERE_PRICES):
                continue
            storefront.append(
                StorefrontItem(
                    item=item,
                    title="🔮 Сфера Мудрости",
                    description=build_wisdom_sphere_description(unlock_count),
                    price_tokens=WISDOM_SPHERE_PRICES[unlock_count],
                    item_type=item.item_type,
                    image_url=get_item_image_url(item),
                )
            )
            continue
        storefront.append(
            StorefrontItem(
                item=item,
                title=item.title,
                description=item.description,
                price_tokens=item.price_tokens,
                item_type=item.item_type,
                image_url=get_item_image_url(item),
            )
        )
    return storefront


async def list_active_items(db: AsyncSession, user: User) -> list[StorefrontItem]:
    return await build_storefront_items(db, user)


async def user_owns_item_type(db: AsyncSession, user: User, item_type: str) -> bool:
    result = await db.execute(
        select(MarketplacePurchase)
        .join(MarketplaceItem, MarketplaceItem.id == MarketplacePurchase.item_id)
        .where(MarketplacePurchase.user_id == user.id, MarketplaceItem.item_type == item_type)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def fallback_recommendation(user: User, level: int) -> str:
    status = user.status or "object"
    recommendations = [
        (
            "Первая сфера открыта.\n\n"
            "Сделай паузу между импульсом и действием. Один раз сегодня не отвечай сразу: "
            "назови свою реакцию, задай один вопрос, только потом формулируй позицию."
        ),
        (
            "Вторая сфера открыта.\n\n"
            "Следи за местами, где ты говоришь гладко, но не точно. Замени одну красивую "
            "формулировку на прямую: «я хочу», «я боюсь», «я избегаю»."
        ),
        (
            "Третья сфера открыта.\n\n"
            "Проверь, где ты уступаешь не из доброты, а из страха потерять одобрение. "
            "Одна фраза на сегодня: «я подумаю и вернусь с ответом»."
        ),
        (
            "Четвертая сфера открыта.\n\n"
            "Твоя следующая зона роста — устойчивость под давлением. Когда эмоция начнет вести, "
            "замедлись, назови факт без обвинения и выдержи паузу дольше обычного."
        ),
        (
            "Пятая сфера открыта.\n\n"
            "Ищи в себе не только убеждения, но и слепые пятна. Возьми одну сильную позицию и "
            "честно допиши: что могло бы меня переубедить и почему я пока этого не допускаю."
        ),
        (
            "Шестая сфера открыта.\n\n"
            "Здесь уже важна не только честность, но и действие. Выбери ситуацию, где ты давно "
            "видишь ложь, но молчишь ради удобства. Сделай один спокойный шаг в сторону правды."
        ),
        (
            "Седьмая сфера открыта.\n\n"
            "Теперь Оракул требует согласия между словом и жизнью. Отметь один повторяющийся "
            "разрыв между твоим образом себя и реальным действием, затем в течение суток закрой "
            "этот разрыв конкретным поступком без свидетелей и без саморекламы."
        ),
    ]
    intro = (
        f"Послание Оракула для статуса «{status}».\n\n"
        "Оно собрано из результатов тестирования, поведения в кейсах и того, "
        "как ты держишь себя в диалоге и под давлением.\n\n"
    )
    return intro + recommendations[min(level, len(recommendations) - 1)]


async def build_wisdom_recommendation(user: User, *, level: int, price_tokens: int) -> str:
    detail_rules = [
        "Дай короткую рекомендацию: 2 абзаца и 1 действие на 24 часа.",
        "Дай плотную рекомендацию: 3 абзаца и 2 конкретных шага на 48 часов.",
        "Дай глубокую рекомендацию: 4 абзаца, опиши паттерн, риск и практику.",
        "Дай насыщенную рекомендацию: 4-5 абзацев, один центральный конфликт и план на 3 дня.",
        "Дай развернутую рекомендацию: 5 абзацев и короткий протокол самонаблюдения.",
        (
            "Дай очень глубокую рекомендацию: 5-6 абзацев, наблюдение, конфликт, "
            "дисциплина, действие."
        ),
        (
            "Дай самую глубокую рекомендацию: 6 абзацев, без воды, "
            "с точным вердиктом и планом на неделю."
        ),
    ]
    try:
        recommendation = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — Оракул ETHOS. Пиши на русском, на «ты», эстетично и точно. "
                        "Не ставь диагнозов, не раскрывай скрытые метрики и не упоминай алгоритм. "
                        "Используй слово «субъектность» и его падежные формы. "
                        "Никогда не используй слово «субъективность» и его падежные формы. "
                        "Формат: только plain text, без Markdown, без HTML, без символов * и **. "
                        "Делай короткие смысловые блоки через пустую строку. "
                        "Не склеивай заголовки, абзацы и нумерованные пункты. "
                        "Если используешь список, каждый пункт начинай с новой строки "
                        "в формате «1. Текст», с пробелом после точки. "
                        "Нужно дать личную рекомендацию на основе психологического портрета, "
                        "тестирования, кейсов и наблюдения за поведением пользователя. "
                        f"{detail_rules[min(level, len(detail_rules) - 1)]}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Ступень Сферы Мудрости: {level + 1}\n"
                        f"Стоимость: {price_tokens} PsyCoin\n"
                        f"Статус: {user.status}\n"
                        f"Индекс субъектности: {user.subjectivity_score}/100\n"
                        "Психологический портрет: "
                        f"{user.profile_summary or 'Портрет еще краткий'}\n"
                        "Сделай выводы о пользователе по наблюдениям Оракула в тестировании, "
                        "кейсах, баттлах и обычном диалоге."
                    ),
                },
            ],
            temperature=0.45,
            max_tokens=900,
        )
        return clean_generated_text(recommendation, split_sections=True)
    except Exception:
        return clean_generated_text(fallback_recommendation(user, level), split_sections=True)


async def purchase_item(
    db: AsyncSession, user: User, storefront_item: StorefrontItem
) -> tuple[bool, str]:
    price_tokens = storefront_item.price_tokens
    if user.token_balance < price_tokens:
        return (
            False,
            f"Пока не хватает псикоинов: нужно {price_tokens}, у вас {user.token_balance}. "
            "Можно пройти /case, /news или баттл в группе.",
        )

    user.token_balance -= price_tokens
    purchase = MarketplacePurchase(
        user_id=user.id,
        item_id=storefront_item.item.id,
        price_tokens=price_tokens,
    )
    db.add(purchase)
    db.add(
        TokenLedgerEntry(
            user_id=user.id,
            amount=-price_tokens,
            reason=f"PsyCoin marketplace purchase: {storefront_item.title}",
        )
    )
    await db.flush()

    if storefront_item.item_type == "wisdom_sphere":
        level = max(0, WISDOM_SPHERE_PRICES.index(price_tokens))
        recommendation = await build_wisdom_recommendation(
            user,
            level=level,
            price_tokens=price_tokens,
        )
        return (
            True,
            f"Сфера Мудрости открыта.\n\n{recommendation}\n\n"
            f"Баланс: {user.token_balance} псикоинов.",
        )

    if storefront_item.item_type.startswith("privilege_"):
        return (
            True,
            f"Привилегия активирована: {storefront_item.title}.\n\n"
            f"Баланс: {user.token_balance} псикоинов.",
        )

    return (
        True,
        f"Коллекционный предмет добавлен в инвентарь: {storefront_item.title}.\n\n"
        f"Баланс: {user.token_balance} псикоинов.",
    )


async def format_shop(db: AsyncSession, user: User) -> str:
    items = await list_active_items(db, user)
    lines = ["Магазин", ""]
    for item in items:
        lines.append(f"{item.title} — {item.price_tokens} псикоинов\n{item.description}")
    lines.append("\nДля покупки: /buy 1")
    return "\n\n".join(lines)


async def buy_item(db: AsyncSession, user: User, index: int) -> str:
    items = await list_active_items(db, user)
    if index < 1 or index > len(items):
        return "Такого предмета нет. Посмотрите витрину: /shop"
    storefront_item = items[index - 1]
    _, message = await purchase_item(db, user, storefront_item)
    return message
