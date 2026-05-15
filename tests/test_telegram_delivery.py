from types import SimpleNamespace
from uuid import uuid4

from app.api.v1 import telegram
from app.schemas.message import (
    ChatAnimationStep,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageResponse,
)
from app.services import telegram_delivery
from app.services.telegram_delivery import (
    ALLOWED_UPDATES,
    direct_webhook_url,
    send_telegram_response,
    split_telegram_text,
    sync_direct_telegram_webhook,
    to_telegram_reply_markup,
)


def test_reply_markup_supports_callback_and_url_buttons() -> None:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="yes"),
                InlineKeyboardButton(text="Чат", url="https://t.me/example"),
            ]
        ]
    )

    assert to_telegram_reply_markup(markup) == {
        "inline_keyboard": [
            [
                {"text": "Да", "callback_data": "yes"},
                {"text": "Чат", "url": "https://t.me/example"},
            ]
        ]
    }


def test_split_telegram_text_keeps_short_message_intact() -> None:
    assert split_telegram_text("Ответ Оракула") == ["Ответ Оракула"]


def test_direct_webhook_url_is_derived_from_public_webapp_url() -> None:
    assert direct_webhook_url().endswith("/api/v1/telegram/direct-webhook")


async def test_send_telegram_response_sends_message_with_markup(monkeypatch) -> None:
    calls = []

    async def fake_telegram_api(method: str, payload: dict) -> dict:
        calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 42}}

    monkeypatch.setattr(telegram_delivery, "telegram_api", fake_telegram_api)
    update = {"message": {"chat": {"id": 123}, "text": "Привет"}}
    response = MessageResponse(
        user_id=uuid4(),
        session_id=uuid4(),
        reply="Ответ Оракула",
        mode="test",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть", url="https://t.me/example")]
            ]
        ),
    )

    await send_telegram_response(update, response, answer_callback=False)

    assert calls == [
        (
            "sendMessage",
            {
                "chat_id": 123,
                "text": "Ответ Оракула",
                "disable_web_page_preview": True,
                "reply_markup": {
                    "inline_keyboard": [[{"text": "Открыть", "url": "https://t.me/example"}]]
                },
            },
        )
    ]


async def test_send_telegram_response_plays_intro_animation(monkeypatch) -> None:
    calls = []

    async def fake_telegram_api(method: str, payload: dict) -> dict:
        calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 77}}

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(telegram_delivery, "telegram_api", fake_telegram_api)
    monkeypatch.setattr(telegram_delivery.asyncio, "sleep", fake_sleep)
    update = {"message": {"chat": {"id": 555}, "text": "/start"}}
    response = MessageResponse(
        user_id=uuid4(),
        session_id=uuid4(),
        reply="Финальный ответ",
        mode="onboarding_start",
        intro_animation=[
            ChatAnimationStep(text="Шаг 1", duration_ms=0),
            ChatAnimationStep(text="Шаг 2", duration_ms=0),
        ],
    )

    await send_telegram_response(update, response, answer_callback=False)

    assert [method for method, _ in calls] == [
        "sendMessage",
        "editMessageText",
        "deleteMessage",
        "sendMessage",
    ]
    assert calls[0][1]["text"] == "Шаг 1"
    assert calls[1][1]["text"] == "Шаг 2"
    assert calls[-1][1]["text"] == "Финальный ответ"


async def test_pre_checkout_response_is_suppressed(monkeypatch) -> None:
    user = SimpleNamespace(
        id=uuid4(),
        subjectivity_score=50,
    )
    session = SimpleNamespace(id=uuid4())
    calls = []

    async def fake_get_or_create_user(db, payload):
        calls.append(("get_user", payload.telegram_id))
        return user

    async def fake_get_active_session(db, user, source):
        calls.append(("get_session", source))
        return session

    async def fake_answer_pre_checkout_query(db, *, pre_checkout_query):
        calls.append(("answer_pre_checkout", pre_checkout_query["id"]))
        return True, ""

    async def fake_add_message(*args, **kwargs):
        calls.append(("add_message", kwargs["content"]))

    class FakeDb:
        async def commit(self) -> None:
            calls.append(("commit", None))

    monkeypatch.setattr(telegram, "get_or_create_user", fake_get_or_create_user)
    monkeypatch.setattr(telegram, "get_active_session", fake_get_active_session)
    monkeypatch.setattr(
        telegram,
        "answer_pre_checkout_query",
        fake_answer_pre_checkout_query,
    )
    monkeypatch.setattr(telegram, "add_message", fake_add_message)

    response = await telegram.build_telegram_response(
        {
            "update_id": 1,
            "pre_checkout_query": {
                "id": "pcq-1",
                "from": {"id": 123, "username": "tester"},
                "invoice_payload": "ethos:test",
                "currency": "XTR",
                "total_amount": 1,
            },
        },
        FakeDb(),
    )

    assert response.mode == "stars_pre_checkout_ok"
    assert response.suppress_reply is True
    assert calls == [
        ("get_user", 123),
        ("get_session", "telegram"),
        ("answer_pre_checkout", "pcq-1"),
        ("add_message", "stars_pre_checkout:ethos:test"),
        ("commit", None),
    ]


async def test_sync_direct_webhook_sets_expected_payload(monkeypatch) -> None:
    calls = []

    async def fake_telegram_api(method: str, payload: dict) -> dict:
        calls.append((method, payload))
        return {"ok": True, "result": True}

    monkeypatch.setattr(telegram_delivery, "telegram_api", fake_telegram_api)
    monkeypatch.setattr(telegram_delivery.settings, "public_webapp_url", "https://example.com/app/shop")
    monkeypatch.setattr(telegram_delivery.settings, "telegram_webhook_secret_token", "secret-token")

    result = await sync_direct_telegram_webhook()

    assert result.startswith("Direct webhook Telegram установлен.")
    assert calls == [
        (
            "setWebhook",
            {
                "url": "https://example.com/api/v1/telegram/direct-webhook",
                "allowed_updates": ALLOWED_UPDATES,
                "drop_pending_updates": False,
                "secret_token": "secret-token",
            },
        )
    ]
