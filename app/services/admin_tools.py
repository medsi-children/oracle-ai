from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.assessment import Assessment
from app.models.marketplace import MarketplacePurchase
from app.models.message import Message
from app.models.session import ConversationSession
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.admin_reset import find_user_for_reset, reset_user_profile


VALID_STATUSES = {"object", "seeker", "faithful", "keeper", "sighted", "subject"}
ADMIN_SUCCESS = "Команда успешно выполнена!"
ADMIN_ERROR = "Команда не выполнена."


def format_admin_success(text: str) -> str:
    return f"{ADMIN_SUCCESS}\n\n{text}"


def format_admin_error(text: str) -> str:
    return f"{ADMIN_ERROR}\n\n{text}"


def format_admin_help() -> str:
    return (
        "Админ-панель ETHOS\n\n"
        "/admin — показать эти команды\n"
        "/users [число] — последние пользователи\n"
        "/user @username — карточка пользователя\n"
        "/reset @username — полностью обнулить профиль\n"
        "/grant @username 10 причина — изменить баланс PsyCoin\n"
        "/addcoins @username 10 причина — начислить PsyCoin\n"
        "/setscore @username 50 — задать индекс субъектности\n"
        "/setstatus @username object — задать статус вручную\n"
        "/close @username — закрыть активные сессии пользователя\n"
        "/shoplink @username — ссылка на mini-app магазина\n"
        "/summary — создать summary по завершенным диалогам\n\n"
        "Админский чат не проходит onboarding, не получает ETHOS-тесты и не попадает "
        "в рассылки/summary."
    )


def user_label(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    if user.telegram_id is not None:
        return f"id {user.telegram_id}"
    return str(user.id)


async def format_users_list(db: AsyncSession, clean: str) -> str:
    parts = clean.split(maxsplit=1)
    limit = 10
    if len(parts) > 1 and parts[1].strip().isdigit():
        limit = min(30, max(1, int(parts[1].strip())))

    result = await db.execute(select(User).order_by(User.created_at.desc()).limit(limit))
    users = list(result.scalars().all())
    if not users:
        return format_admin_success("Пользователей пока нет.")

    lines = ["Пользователи:"]
    for user in users:
        lines.append(
            f"{user_label(user)} | {user.status} | {user.subjectivity_score}/100 | "
            f"{user.token_balance} PsyCoin"
        )
    return format_admin_success("\n".join(lines))


async def format_user_card(db: AsyncSession, clean: str) -> str:
    target = await user_from_command(db, clean)
    if target is None:
        return format_admin_error("Пользователь не найден. Формат: /user @username или /user telegram_id")

    sessions_count = await scalar_count(
        db, select(func.count()).select_from(ConversationSession).where(ConversationSession.user_id == target.id)
    )
    messages_count = await scalar_count(
        db, select(func.count()).select_from(Message).where(Message.user_id == target.id)
    )
    assessments_count = await scalar_count(
        db, select(func.count()).select_from(Assessment).where(Assessment.user_id == target.id)
    )
    purchases_count = await scalar_count(
        db,
        select(func.count())
        .select_from(MarketplacePurchase)
        .where(MarketplacePurchase.user_id == target.id),
    )
    active_sessions = await scalar_count(
        db,
        select(func.count())
        .select_from(ConversationSession)
        .where(ConversationSession.user_id == target.id, ConversationSession.state != "closed"),
    )

    summary = target.profile_summary or "Профиль пока пустой."
    return format_admin_success(
        f"{user_label(target)}\n\n"
        f"Telegram ID: {target.telegram_id}\n"
        f"Статус: {target.status}\n"
        f"Индекс субъектности: {target.subjectivity_score}/100\n"
        f"Баланс: {target.token_balance} PsyCoin\n\n"
        f"Сессии: {sessions_count} (активных: {active_sessions})\n"
        f"Сообщения: {messages_count}\n"
        f"Оценки: {assessments_count}\n"
        f"Покупки: {purchases_count}\n\n"
        f"{summary[:1000]}"
    )


async def scalar_count(db: AsyncSession, query) -> int:
    result = await db.execute(query)
    return int(result.scalar_one() or 0)


async def user_from_command(db: AsyncSession, clean: str) -> User | None:
    parts = clean.split(maxsplit=1)
    if len(parts) < 2:
        return None
    return await find_user_for_reset(db, parts[1].split(maxsplit=1)[0])


async def reset_command(db: AsyncSession, clean: str, *, admin: User) -> str:
    target = await user_from_command(db, clean)
    if target is None:
        return format_admin_error("Пользователь не найден. Формат: /reset @username или /reset telegram_id")
    if target.id == admin.id:
        return format_admin_error("Свой профиль через /reset не стираю, чтобы не оставить проект без админа.")

    label = user_label(target)
    await reset_user_profile(db, target)
    return format_admin_success(
        f"Профиль {label} полностью обнулен.\n\n"
        "Удалены история, сессии, оценки, summary, покупки и ledger псикоинов. "
        "Статус: Объект. Баланс: 0."
    )


async def grant_command(db: AsyncSession, clean: str) -> str:
    parts = clean.split(maxsplit=3)
    if len(parts) < 3:
        return format_admin_error("Формат: /grant @username 10 причина")

    target = await find_user_for_reset(db, parts[1])
    if target is None:
        return format_admin_error("Пользователь не найден.")
    try:
        amount = int(parts[2])
    except ValueError:
        return format_admin_error("Сумма должна быть целым числом, например: /grant @user 10 тест")

    reason = parts[3].strip() if len(parts) > 3 else "Admin balance adjustment"
    target.token_balance = max(0, target.token_balance + amount)
    db.add(
        TokenLedgerEntry(
            user_id=target.id,
            amount=amount,
            reason=f"Admin: {reason}",
        )
    )
    return format_admin_success(
        f"Баланс {user_label(target)} изменен на {amount}. Сейчас: {target.token_balance} PsyCoin."
    )


async def setscore_command(db: AsyncSession, clean: str) -> str:
    parts = clean.split(maxsplit=2)
    if len(parts) < 3:
        return format_admin_error("Формат: /setscore @username 50")
    target = await find_user_for_reset(db, parts[1])
    if target is None:
        return format_admin_error("Пользователь не найден.")
    try:
        score = max(0, min(100, int(parts[2])))
    except ValueError:
        return format_admin_error("Индекс должен быть числом от 0 до 100.")
    target.subjectivity_score = score
    return format_admin_success(f"Индекс субъектности {user_label(target)} установлен: {score}/100.")


async def setstatus_command(db: AsyncSession, clean: str) -> str:
    parts = clean.split(maxsplit=2)
    if len(parts) < 3:
        return format_admin_error("Формат: /setstatus @username object")
    target = await find_user_for_reset(db, parts[1])
    if target is None:
        return format_admin_error("Пользователь не найден.")
    status = parts[2].strip().lower()
    if status not in VALID_STATUSES:
        return format_admin_error("Статус должен быть одним из: " + ", ".join(sorted(VALID_STATUSES)))
    target.status = status
    return format_admin_success(f"Статус {user_label(target)} установлен: {status}.")


async def close_sessions_command(db: AsyncSession, clean: str) -> str:
    target = await user_from_command(db, clean)
    if target is None:
        return format_admin_error("Пользователь не найден. Формат: /close @username")

    result = await db.execute(
        select(ConversationSession).where(
            ConversationSession.user_id == target.id,
            ConversationSession.state != "closed",
        )
    )
    sessions = list(result.scalars().all())
    for session in sessions:
        session.state = "closed"
    return format_admin_success(f"Закрыто активных сессий для {user_label(target)}: {len(sessions)}.")


async def shoplink_command(db: AsyncSession, clean: str) -> str:
    target = await user_from_command(db, clean)
    if target is None or target.telegram_id is None:
        return format_admin_error("Пользователь не найден. Формат: /shoplink @username")
    return format_admin_success(settings.public_webapp_url + f"?telegram_id={target.telegram_id}")


async def handle_admin_tool_command(db: AsyncSession, admin: User, clean: str) -> str | None:
    command = clean.split(maxsplit=1)[0].lower()
    if command in {"/admin", "/help"}:
        return format_admin_help()
    if command == "/users":
        return await format_users_list(db, clean)
    if command == "/user":
        return await format_user_card(db, clean)
    if command == "/reset":
        return await reset_command(db, clean, admin=admin)
    if command in {"/grant", "/addcoins"}:
        return await grant_command(db, clean)
    if command == "/setscore":
        return await setscore_command(db, clean)
    if command == "/setstatus":
        return await setstatus_command(db, clean)
    if command == "/close":
        return await close_sessions_command(db, clean)
    if command == "/shoplink":
        return await shoplink_command(db, clean)
    return None
