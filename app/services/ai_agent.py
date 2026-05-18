from __future__ import annotations

from app.services.llm import clean_generated_text, openrouter_chat


ACTIVITY_LABELS = {
    "battle": "баттл ETHOS",
    "case": "разбор кейса",
    "news": "разбор новости",
}


def fallback_ai_agent_reply(activity_type: str) -> str:
    if activity_type == "battle":
        return (
            "Слушай, я бы с этим поспорил. В твоей позиции есть стержень, но пока не видно, "
            "что ты готов сделать, когда станет неудобно.\n\n"
            "Попробуй без красивой рамки: где здесь твоя личная ответственность?"
        )
    if activity_type == "news":
        return (
            "Я бы не спешил вставать в строй с первой реакцией. Новость легко дергает за "
            "нерв, а потом человек уже защищает не правду, а свое раздражение.\n\n"
            "Что ты точно знаешь, а что просто почувствовал?"
        )
    return (
        "Я слышу ход мысли, но он пока слишком ровный. Как будто ты описал правильную "
        "позицию, а не свой настоящий выбор.\n\n"
        "Где в этом кейсе место, в котором тебе самому было бы неприятно поступить честно?"
    )


async def generate_ai_agent_reply(
    *,
    activity_type: str,
    prompt: str,
    user_text: str,
    previous_agent_text: str | None = None,
) -> str:
    activity_label = ACTIVITY_LABELS.get(activity_type, "разбор")
    try:
        parts = [
            f"Формат: {activity_label}.",
            f"Тема или кейс:\n{prompt}",
            f"Позиция человека:\n{user_text}",
        ]
        if previous_agent_text:
            parts.append(f"Твой предыдущий ответ:\n{previous_agent_text}")
        raw = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — Оракул ETHOS, но сейчас играешь роль живого оппонента, "
                        "а не судьи и не справочного сервиса. Отвечай по-русски как человек "
                        "в напряженном споре о выборе и последствиях: коротко, естественно, с небольшой "
                        "шероховатостью речи. Не полируй фразы до рекламного блеска. "
                        "Можно использовать 'слушай', 'я бы тут поспорил', 'вот где мне "
                        "не сходится', но без хамства и унижения. Не говори, что ты ИИ, "
                        "модель или нейросеть. Не ставь оценки, не начисляй псикоины, "
                        "не используй Markdown. 2-5 коротких фраз, затем один точный вопрос."
                    ),
                },
                {"role": "user", "content": "\n\n".join(parts)},
            ],
            temperature=0.82,
            max_tokens=360,
        )
        reply = clean_generated_text(raw)
        return reply or fallback_ai_agent_reply(activity_type)
    except Exception:
        return fallback_ai_agent_reply(activity_type)
