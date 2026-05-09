from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case

SEED_CASES = [
    {
        "title": "Неловкая правда",
        "category": "ethics",
        "difficulty": 1,
        "prompt": (
            "Вы замечаете, что близкий человек публично повторяет очевидно неверный факт. "
            "Если поправить его сразу, ему будет стыдно. Если промолчать, ошибка пойдет дальше. "
            "Что вы сделаете и почему?"
        ),
    },
    {
        "title": "Давление группы",
        "category": "communication",
        "difficulty": 1,
        "prompt": (
            "В компании начинают жестко высмеивать человека, которого рядом нет. "
            "Все смеются, и от вас тоже ждут участия. Как вы сохраните себя и контакт с группой?"
        ),
    },
    {
        "title": "Собственная ошибка",
        "category": "self_reflection",
        "difficulty": 1,
        "prompt": (
            "Вы понимаете, что в споре защищали позицию не потому, что она верная, "
            "а потому что боялись потерять лицо. Что будет зрелым следующим шагом?"
        ),
    },
    {
        "title": "Помощь без спектакля",
        "category": "empathy",
        "difficulty": 2,
        "prompt": (
            "Человек рядом явно нуждается в поддержке, но не просит о помощи. "
            "Как отличить деятельную эмпатию от навязчивого спасательства?"
        ),
    },
    {
        "title": "Цена молчания",
        "category": "historical_awareness",
        "difficulty": 2,
        "prompt": (
            "Вы видите несправедливость, но прямое вмешательство может повредить вашим отношениям "
            "или положению. Где проходит граница между осторожностью и участием во лжи?"
        ),
    },
]


async def ensure_seed_cases(db: AsyncSession) -> None:
    result = await db.execute(select(func.count()).select_from(Case))
    count = result.scalar_one()
    if count:
        return

    for item in SEED_CASES:
        db.add(Case(**item))
    await db.flush()


async def get_random_case(db: AsyncSession) -> Case:
    await ensure_seed_cases(db)
    result = await db.execute(
        select(Case).where(Case.is_active.is_(True)).order_by(func.random()).limit(1)
    )
    case = result.scalar_one()
    return case
