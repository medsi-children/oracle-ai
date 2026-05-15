from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.daily_tasks import (
    MORNING_QUESTION_PREFIX,
    compact_oracle_thoughts,
    morning_fallback_question,
    morning_question_is_valid,
    morning_question_replacement_requested,
    process_morning_case_response,
)
from app.services.dialogue import (
    format_confirmation_prompt,
    format_mode_prompt,
    game_mode_reply_markup,
    get_pending_game,
    set_pending_game,
    stake_reply_markup,
    update_pending_game,
)
from app.services.scheduler import seconds_until_next_morning_run


def test_game_mode_prompt_asks_for_ai_or_human() -> None:
    text = format_mode_prompt("battle")
    markup = game_mode_reply_markup()
    buttons = [button.text for row in markup.inline_keyboard for button in row]

    assert "Желаете сразиться в соло с ИИ-агентом или с человеком?" in text
    assert "С ИИ-агентом" in buttons
    assert "С человеком" in buttons


def test_stake_markup_offers_psycoin_levels_and_manual_choice() -> None:
    buttons = [button.text for row in stake_reply_markup().inline_keyboard for button in row]

    assert "1 псикоин" in buttons
    assert "100 псикоинов" in buttons
    assert "Другая ставка" in buttons


def test_pending_game_payload_survives_mode_and_stake_updates() -> None:
    session = SimpleNamespace(state="active", summary=None)

    set_pending_game(session, action="news", topic="тест", chat_type="group")
    update_pending_game(session, mode="ai")
    pending = update_pending_game(session, stake=5)

    assert session.state == "game:mode"
    assert pending == get_pending_game(session)
    assert pending["action"] == "news"
    assert pending["mode"] == "ai"
    assert pending["stake"] == 5
    assert "Ставка: 5 псикоинов" in format_confirmation_prompt(pending)


def test_morning_question_prefix_and_fallback_are_safe() -> None:
    assert MORNING_QUESTION_PREFIX == (
        "У Оракула для вас вопрос. Ответьте на него и заработаете псикоины."
    )
    assert morning_question_is_valid(morning_fallback_question())
    assert not morning_question_is_valid("Ты субъект или объект?")
    assert not morning_question_is_valid("Что выберет терпила?")


def test_morning_question_replacement_request_is_detected() -> None:
    assert morning_question_replacement_requested("Не понимаю вопрос, дайте другой")
    assert morning_question_replacement_requested("Можно другой?")
    assert morning_question_replacement_requested("Можно новый вопрос?")
    assert not morning_question_replacement_requested(
        "Я отвечу спокойно и задам уточняющий вопрос"
    )


def test_oracle_thoughts_are_compact() -> None:
    summary = (
        "В ответе видно, что вы не бросаетесь в спор сразу. "
        "Сильная сторона — попытка назвать границу спокойно. "
        "Зона роста: добавить конкретную фразу."
    )

    assert compact_oracle_thoughts(summary) == (
        "В ответе видно, что вы не бросаетесь в спор сразу. "
        "Сильная сторона — попытка назвать границу спокойно."
    )


async def test_morning_response_returns_dialogue_contract(monkeypatch) -> None:
    async def fake_create_assessment(*args, **kwargs):
        return (
            SimpleNamespace(
                id=uuid4(),
                summary="Вы выбрали спокойный первый шаг. Это снижает риск лишнего конфликта.",
            ),
            0,
        )

    class FakeDb:
        def __init__(self) -> None:
            self.added = []

        def add(self, item) -> None:
            self.added.append(item)

        async def flush(self) -> None:
            return None

    monkeypatch.setattr(
        "app.services.daily_tasks.create_assessment",
        fake_create_assessment,
    )
    monkeypatch.setattr(
        "app.services.daily_tasks.assessment_average_score",
        lambda assessment: 80,
    )
    user = SimpleNamespace(
        id=uuid4(),
        token_balance=0,
        subjectivity_score=50,
        status="object",
    )
    db = FakeDb()

    reply, mode, token_delta, markup = await process_morning_case_response(
        db,
        user,
        "Отвечу спокойно и уточню, что именно нужно переделать.",
        question="Утренний вопрос",
    )

    assert reply.startswith("Спасибо за ваш ответ.")
    assert "Мысли Оракула:" in reply
    assert "Вы заработали:" in reply
    assert mode == "morning_case_assessment"
    assert token_delta == 4
    assert markup is None
    assert user.token_balance == 4
    assert len(db.added) == 1


def test_system_entry_default_price_is_ten_stars() -> None:
    assert settings.system_entry_star_price == 10


def test_scheduler_targets_ten_oclock_moscow() -> None:
    now = datetime(2026, 5, 14, 9, 30, tzinfo=ZoneInfo("Europe/Moscow"))

    assert seconds_until_next_morning_run(now) == 30 * 60
