from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings
from app.schemas.message import InlineKeyboardMarkup, MessageResponse, OutgoingMessage
from app.services.stars import TelegramStarsError, telegram_api

logger = logging.getLogger(__name__)
ALLOWED_UPDATES = ["message", "callback_query", "pre_checkout_query"]
MAX_TELEGRAM_TEXT = 3900


def telegram_base_url() -> str:
    public_url = settings.public_webapp_url.strip().rstrip("/")
    if public_url.endswith("/app/shop"):
        return public_url[: -len("/app/shop")]
    return public_url


def direct_webhook_url() -> str:
    return f"{telegram_base_url()}{settings.api_v1_prefix}/telegram/direct-webhook"


def extract_chat_id(update: dict[str, Any]) -> int | None:
    callback_query = update.get("callback_query") or {}
    message = update.get("message") or callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    return int(chat_id) if chat_id is not None else None


def extract_callback_query_id(update: dict[str, Any]) -> str | None:
    callback_query = update.get("callback_query") or {}
    callback_id = callback_query.get("id")
    return str(callback_id) if callback_id else None


def to_telegram_reply_markup(markup: InlineKeyboardMarkup | None) -> dict | None:
    if markup is None:
        return None
    rows: list[list[dict[str, Any]]] = []
    for row in markup.inline_keyboard:
        buttons: list[dict[str, Any]] = []
        for button in row:
            if button.web_app:
                buttons.append({"text": button.text, "web_app": button.web_app})
            elif button.url:
                buttons.append({"text": button.text, "url": button.url})
            elif button.callback_data:
                buttons.append({"text": button.text, "callback_data": button.callback_data})
        if buttons:
            rows.append(buttons)
    if not rows:
        return None
    return {"inline_keyboard": rows}


def split_telegram_text(text: str) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    chunks: list[str] = []
    remaining = clean
    while len(remaining) > MAX_TELEGRAM_TEXT:
        split_at = remaining.rfind("\n\n", 0, MAX_TELEGRAM_TEXT)
        if split_at < MAX_TELEGRAM_TEXT // 2:
            split_at = remaining.rfind("\n", 0, MAX_TELEGRAM_TEXT)
        if split_at < MAX_TELEGRAM_TEXT // 2:
            split_at = MAX_TELEGRAM_TEXT
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def answer_callback_query(update: dict[str, Any]) -> None:
    callback_id = extract_callback_query_id(update)
    if callback_id is None:
        return
    try:
        await telegram_api(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_id,
                "text": "Принято",
                "cache_time": 0,
            },
        )
    except TelegramStarsError:
        logger.exception("Failed to answer callback query")


async def send_message(
    *,
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return await telegram_api("sendMessage", payload)


async def send_outgoing_message(chat_id: int, message: OutgoingMessage) -> None:
    chunks = split_telegram_text(message.text)
    if not chunks:
        return
    reply_markup = to_telegram_reply_markup(message.reply_markup)
    for index, chunk in enumerate(chunks):
        await send_message(
            chat_id=chat_id,
            text=chunk,
            reply_markup=reply_markup if index == len(chunks) - 1 else None,
            parse_mode="HTML",
        )

async def delete_message(*, chat_id: int, message_id: int) -> None:

    try:

        await telegram_api(

            "deleteMessage",

            {

                "chat_id": chat_id,

                "message_id": message_id,

            },

        )

    except TelegramStarsError:

        logger.exception("Failed to delete telegram message")

async def play_intro_animation(chat_id: int, response: MessageResponse) -> None:
    intro = response.intro_animation or []
    if not intro:
        return
    first = intro[0]
    sent = await send_message(chat_id=chat_id, text=first.text, parse_mode=first.parse_mode)
    message = sent.get("result") or {}
    message_id = message.get("message_id")
    if message_id is None:
        return

    previous_duration = first.duration_ms
    for step in intro[1:]:
        await asyncio.sleep(max(0, previous_duration) / 1000)
        try:
            await telegram_api(
                "editMessageText",
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": step.text,
                    "parse_mode": step.parse_mode,
                },
            )
        except TelegramStarsError:
            logger.exception("Failed to edit intro message")
            break
        previous_duration = step.duration_ms

    await asyncio.sleep(max(0, previous_duration) / 1000)
    try:
        await telegram_api(
            "deleteMessage",
            {
                "chat_id": chat_id,
                "message_id": message_id,
            },
        )
    except TelegramStarsError:
        logger.exception("Failed to delete intro message")


async def send_telegram_response(
    update: dict[str, Any],
    response: MessageResponse,
    *,
    answer_callback: bool = True,
) -> None:
    if answer_callback:
        await answer_callback_query(update)

    if response.suppress_reply:
        return

    chat_id = extract_chat_id(update)

    if chat_id is None:
        logger.warning("Telegram response has no chat_id; mode=%s", response.mode)
        return

    await play_intro_animation(chat_id, response)

    loading_message_id = None

    if response.loading_message:
        loading_response = await send_message(
            chat_id=chat_id,
            text=response.loading_message,
            parse_mode=response.loading_parse_mode,
        )

        loading_result = loading_response.get("result") or {}
        loading_message_id = loading_result.get("message_id")

    chunks = split_telegram_text(response.reply)

    if not chunks:
        return

    if loading_message_id is not None:
        await delete_message(
            chat_id=chat_id,
            message_id=loading_message_id,
        )

    for extra_message in response.extra_messages:
        await send_outgoing_message(chat_id, extra_message)

    await send_outgoing_message(
        chat_id,
        OutgoingMessage(text=response.reply, reply_markup=response.reply_markup),
    )


async def sync_direct_telegram_webhook() -> str:
    webhook_url = direct_webhook_url()
    if not webhook_url.startswith("https://"):
        return "Direct webhook не установлен: PUBLIC_WEBAPP_URL должен быть HTTPS."
    payload: dict[str, Any] = {
        "url": webhook_url,
        "allowed_updates": ALLOWED_UPDATES,
        "drop_pending_updates": False,
    }
    if settings.telegram_webhook_secret_token.strip():
        payload["secret_token"] = settings.telegram_webhook_secret_token.strip()
    try:
        await telegram_api("setWebhook", payload)
    except TelegramStarsError as exc:
        return f"Telegram не принял direct webhook: {exc}"
    return (
        "Direct webhook Telegram установлен.\n\n"
        f"{webhook_url}\n\n"
        "Теперь можно отключить n8n workflow с Telegram Trigger."
    )


async def get_direct_telegram_webhook_info() -> str:
    try:
        data = await telegram_api("getWebhookInfo", {})
    except TelegramStarsError as exc:
        return f"Не удалось получить webhook info: {exc}"
    info = data.get("result") or {}
    return (
        "Telegram webhook info\n\n"
        f"URL: {info.get('url') or 'не установлен'}\n"
        f"Pending updates: {info.get('pending_update_count', 0)}\n"
        f"Last error: {info.get('last_error_message') or 'нет'}"
    )
