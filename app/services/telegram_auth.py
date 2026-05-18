from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from app.core.config import settings


class TelegramWebAppAuthError(ValueError):
    pass


def _allow_local_telegram_id_fallback() -> bool:
    public_url = settings.public_webapp_url.lower()
    return settings.app_env.lower() == "local" and (
        "localhost" in public_url or "127.0.0.1" in public_url
    )


def verify_telegram_webapp_user(init_data: str | None, telegram_id: int) -> None:
    if not init_data:
        if _allow_local_telegram_id_fallback():
            return
        raise TelegramWebAppAuthError("Telegram initData is required")

    token = settings.telegram_bot_token.strip()
    if not token:
        if _allow_local_telegram_id_fallback():
            return
        raise TelegramWebAppAuthError("TELEGRAM_BOT_TOKEN is required")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise TelegramWebAppAuthError("Telegram initData hash is missing")

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramWebAppAuthError("Telegram initData hash is invalid")

    try:
        user_payload = json.loads(values.get("user") or "{}")
    except json.JSONDecodeError as exc:
        raise TelegramWebAppAuthError("Telegram initData user is invalid") from exc
    if int(user_payload.get("id") or 0) != telegram_id:
        raise TelegramWebAppAuthError("Telegram user mismatch")
