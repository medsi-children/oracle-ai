from app.core.config import settings
from app.models.user import User


def admin_ids() -> set[int]:
    ids: set[int] = set()
    for raw in settings.admin_telegram_ids.split(","):
        raw = raw.strip()
        if raw.isdigit():
            ids.add(int(raw))
    return ids


def is_admin(user: User) -> bool:
    telegram_id = getattr(user, "telegram_id", None)
    username = getattr(user, "username", None)
    if telegram_id in admin_ids():
        return True
    return (username or "").lower() == settings.admin_telegram_username.lower()


def normalize_username(value: str) -> str:
    return value.strip().lstrip("@").lower()
