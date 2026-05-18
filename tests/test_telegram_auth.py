import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from app.services import telegram_auth
from app.services.telegram_auth import TelegramWebAppAuthError, verify_telegram_webapp_user


def signed_init_data(*, telegram_id: int, token: str) -> str:
    values = {
        "auth_date": "1710000000",
        "query_id": "test-query",
        "user": json.dumps({"id": telegram_id, "first_name": "Tester"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_verify_telegram_webapp_user_accepts_signed_user(monkeypatch) -> None:
    monkeypatch.setattr(telegram_auth.settings, "app_env", "production")
    monkeypatch.setattr(telegram_auth.settings, "telegram_bot_token", "secret-token")

    verify_telegram_webapp_user(
        signed_init_data(telegram_id=123, token="secret-token"),
        123,
    )


def test_verify_telegram_webapp_user_rejects_mismatched_user(monkeypatch) -> None:
    monkeypatch.setattr(telegram_auth.settings, "app_env", "production")
    monkeypatch.setattr(telegram_auth.settings, "telegram_bot_token", "secret-token")

    with pytest.raises(TelegramWebAppAuthError):
        verify_telegram_webapp_user(
            signed_init_data(telegram_id=123, token="secret-token"),
            456,
        )


def test_verify_telegram_webapp_user_allows_local_fallback(monkeypatch) -> None:
    monkeypatch.setattr(telegram_auth.settings, "app_env", "local")
    monkeypatch.setattr(telegram_auth.settings, "public_webapp_url", "http://localhost:8000/app/shop")

    verify_telegram_webapp_user(None, 123)


def test_verify_telegram_webapp_user_rejects_public_url_without_init_data(monkeypatch) -> None:
    monkeypatch.setattr(telegram_auth.settings, "app_env", "local")
    monkeypatch.setattr(telegram_auth.settings, "public_webapp_url", "https://example.com/app/shop")

    with pytest.raises(TelegramWebAppAuthError):
        verify_telegram_webapp_user(None, 123)
