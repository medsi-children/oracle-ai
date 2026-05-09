from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem
from app.services.llm import openrouter_chat


async def get_or_create_news_case(db: AsyncSession) -> NewsItem:
    result = await db.execute(
        select(NewsItem).where(NewsItem.is_active.is_(True)).order_by(NewsItem.created_at.desc()).limit(1)
    )
    item = result.scalar_one_or_none()
    if item is not None:
        return item

    try:
        text = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Придумай новостной этический кейс в стиле Sentinel Mode, но без ссылок "
                        "на конкретные непроверенные факты. Верни 3 блока: Заголовок, Контекст, Кейс. "
                        "Тема должна проверять достоинство, манипуляцию, ответственность и способность "
                        "видеть сложность."
                    ),
                },
                {"role": "user", "content": "Создай один актуально звучащий моральный кейс."},
            ],
            temperature=0.6,
            max_tokens=650,
        )
    except Exception:
        text = (
            "Заголовок: Информационный шум и личная ответственность\n\n"
            "Контекст: В публичном пространстве появляется конфликтная новость. "
            "Люди быстро занимают позиции, часто не проверяя источники.\n\n"
            "Кейс: Как вы решите, когда нужно высказаться, когда промолчать, "
            "и где проходит граница между осторожностью и уходом от ответственности?"
        )

    item = NewsItem(
        title="Sentinel Mode: новостной этический кейс",
        source="oracle_generated",
        summary=text,
        ethical_case=text,
    )
    db.add(item)
    await db.flush()
    return item
