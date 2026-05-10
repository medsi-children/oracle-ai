from __future__ import annotations

import random
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from html import unescape

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem
from app.services.llm import clean_generated_text, openrouter_chat

NEWS_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
]


async def fetch_world_news_candidates() -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        for source, url in NEWS_FEEDS:
            try:
                response = await client.get(url)
                response.raise_for_status()
                root = ET.fromstring(response.text)
            except Exception:
                continue
            for item in root.findall(".//item")[:8]:
                title = unescape(item.findtext("title") or "").strip()
                link = unescape(item.findtext("link") or "").strip()
                description = unescape(item.findtext("description") or "").strip()
                if title:
                    candidates.append(
                        {
                            "source": source,
                            "title": title,
                            "url": link,
                            "summary": description[:700] or title,
                        }
                    )
    return candidates


async def build_news_case(candidate: dict[str, str]) -> str:
    source_line = f"Источник: {candidate['source']}"
    if candidate.get("url"):
        source_line += f"\nСсылка: {candidate['url']}"
    try:
        return await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — редактор Sentinel Mode. По реальной новости создай короткий "
                        "этический кейс на русском. Не выдумывай факты сверх входных данных. "
                        "Структура: Новость, Дилемма, Вопрос. Тон спокойный, без пропаганды."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{source_line}\n"
                        f"Заголовок: {candidate['title']}\n"
                        f"Кратко: {candidate['summary']}"
                    ),
                },
            ],
            temperature=0.35,
            max_tokens=650,
        )
    except Exception:
        return (
            f"Новость: {candidate['title']}\n"
            f"{source_line}\n\n"
            "Дилемма: публичная реакция на новость часто рождается быстрее проверки фактов. "
            "Здесь важно отделить ответственность от импульса и солидарность от толпы.\n\n"
            "Вопрос: какую позицию вы займете сейчас, что проверите перед высказыванием, "
            "и какое действие будет честнее молчаливого согласия?"
        )


async def get_or_create_news_case(db: AsyncSession) -> NewsItem:
    result = await db.execute(
        select(NewsItem)
        .where(NewsItem.is_active.is_(True))
        .order_by(NewsItem.created_at.desc())
        .limit(1)
    )
    item = result.scalar_one_or_none()
    if item is not None and item.created_at >= datetime.now(UTC) - timedelta(hours=6):
        return item

    candidates = await fetch_world_news_candidates()
    if candidates:
        candidate = random.choice(candidates[:12])
        ethical_case = await build_news_case(candidate)
        item = NewsItem(
            title=candidate["title"][:300],
            source=candidate["source"],
            url=candidate.get("url"),
            summary=candidate["summary"],
            ethical_case=ethical_case,
        )
        db.add(item)
        await db.flush()
        return item

    try:
        text = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Придумай новостной этический кейс в стиле Sentinel Mode, но без ссылок "
                        "на конкретные непроверенные факты. Верни 3 блока: "
                        "Заголовок, Контекст, Кейс. "
                        "Тема должна проверять достоинство, манипуляцию, "
                        "ответственность и способность "
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


async def create_custom_news_case(db: AsyncSession, topic: str) -> NewsItem:
    title = topic.strip()[:300] or "Пользовательский новостной разбор"
    try:
        text = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты создаешь разбор Sentinel Mode на русском по заданной пользователем "
                        "новости или теме. Верни plain text без markdown. "
                        "Структура: Новость, Дилемма, Вопрос. Не выдумывай лишних фактов, "
                        "если вход короткий или неполный."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Тема или новость для разбора: {topic.strip()}",
                },
            ],
            temperature=0.35,
            max_tokens=600,
        )
        ethical_case = clean_generated_text(text, split_sections=True)
    except Exception:
        ethical_case = (
            f"Новость\n\n{topic.strip()}\n\n"
            "Дилемма\n\n"
            "Нужно отделить факт от реакции, а личную позицию от желания просто "
            "примкнуть к шуму.\n\n"
            "Вопрос\n\n"
            "Что здесь требует ответственности, что стоит проверить, "
            "и какой выбор сохранит достоинство?"
        )

    item = NewsItem(
        title=title,
        source="user_custom",
        summary=ethical_case,
        ethical_case=ethical_case,
        is_active=False,
    )
    db.add(item)
    await db.flush()
    return item
