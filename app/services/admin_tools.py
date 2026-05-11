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
from app.services.assessment import calculate_status
from app.services.stars import display_user, list_pending_withdrawals, mark_withdrawal_done
from app.services.telegram_delivery import (
    get_direct_telegram_webhook_info,
    sync_direct_telegram_webhook,
)
from app.services.telegram_menu import sync_telegram_bot_commands

VALID_STATUSES = {"object", "seeker", "faithful", "keeper", "sighted", "subject"}
VALID_LIFECYCLE_STATUSES = {"newbie", "beginner", "follower", "admin"}
ADMIN_SUCCESS = "Команда успешно выполнена!"
ADMIN_ERROR = "Команда не выполнена."


def format_admin_success(text: str) -> str:
    return f"{ADMIN_SUCCESS}\n\n{text}"


def format_admin_error(text: str) -> str:
    return f"{ADMIN_ERROR}\n\n{text}"


def format_admin_help(*, success_prefix: bool = True) -> str:
    text = (
        "Админ-панель ETHOS\n\n"
        "/admin — показать эти команды\n"
        "/users [число] — последние пользователи\n"
        "/user @username — карточка пользователя\n"
        "/reset @username — полностью обнулить профиль\n"
        "/grant @username 10 причина — изменить баланс псикоинов\n"
        "/addcoins @username 10 причина — начислить псикоины\n"
        "/setscore @username 50 — задать индекс субъектности\n"
        "/setstatus @username object — задать статус вручную\n"
        "/setlifecycle @username follower — задать этап доступа\n"
        "/close @username — закрыть активные сессии пользователя\n"
        "/shoplink @username — ссылка на mini-app магазина\n"
        "/withdrawals — заявки на вывод звезд\n"
        "/withdrawdone id — отметить заявку выплаченной\n"
        "/synccommands — обновить меню команд Telegram\n"
        "/syncwebhook — подключить Telegram напрямую к backend\n"
        "/webhookinfo — проверить текущий Telegram webhook"
    )
    return format_admin_success(text) if success_prefix else text


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
            f"{user_label(user)} | {user.lifecycle_status} | {user.status} | {user.subjectivity_score}/100 | "
            f"{user.token_balance} псикоинов"
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
        f"Внутренний статус: {target.lifecycle_status}\n"
        f"Статус: {target.status}\n"
        f"Индекс субъектности: {target.subjectivity_score}/100\n"
        f"Баланс: {target.token_balance} псикоинов\n\n"
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
        "Удалены история, сессии, оценки, покупки, заявки на вывод звезд и ledger псикоинов. "
        "Внутренний статус: newbie. Статус: Объект. Баланс: 0."
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
    target.status = calculate_status(target.subjectivity_score, target.token_balance)
    db.add(
        TokenLedgerEntry(
            user_id=target.id,
            amount=amount,
            reason=f"Admin: {reason}",
        )
    )
    return format_admin_success(
        f"Баланс {user_label(target)} изменен на {amount}. Сейчас: {target.token_balance} псикоинов."
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
    target.status = calculate_status(target.subjectivity_score, target.token_balance)
    return format_admin_success(
        f"Индекс субъектности {user_label(target)} установлен: {score}/100.\n"
        f"Статус пересчитан: {target.status}."
    )


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


async def setlifecycle_command(db: AsyncSession, clean: str) -> str:
    parts = clean.split(maxsplit=2)
    if len(parts) < 3:
        return format_admin_error("Формат: /setlifecycle @username follower")
    target = await find_user_for_reset(db, parts[1])
    if target is None:
        return format_admin_error("Пользователь не найден.")
    lifecycle_status = parts[2].strip().lower()
    if lifecycle_status not in VALID_LIFECYCLE_STATUSES:
        return format_admin_error(
            "Внутренний статус должен быть одним из: "
            + ", ".join(sorted(VALID_LIFECYCLE_STATUSES))
        )
    target.lifecycle_status = lifecycle_status
    return format_admin_success(
        f"Внутренний статус {user_label(target)} установлен: {lifecycle_status}."
    )


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


async def withdrawals_command(db: AsyncSession) -> str:
    rows = await list_pending_withdrawals(db)
    if not rows:
        return format_admin_success("Активных заявок на вывод звезд нет.")
    lines = ["Заявки на вывод звезд:"]
    for request, user in rows:
        lines.append(
            f"{request.id} | {display_user(user)} | "
            f"{request.token_amount} псикоинов = {request.star_amount} ⭐"
        )
    return format_admin_success("\n".join(lines))


async def withdrawdone_command(db: AsyncSession, clean: str) -> str:
    parts = clean.split(maxsplit=1)
    if len(parts) < 2:
        return format_admin_error("Формат: /withdrawdone id")
    request = await mark_withdrawal_done(db, parts[1].strip())
    if request is None:
        return format_admin_error("Заявка не найдена.")
    return format_admin_success(
        f"Заявка {request.id} отмечена как выплаченная: {request.star_amount} ⭐."
    )


async def syncwebhook_command() -> str:
    result = await sync_direct_telegram_webhook()
    if result.startswith("Direct webhook Telegram установлен."):
        return format_admin_success(result)
    return format_admin_error(result)


async def webhookinfo_command() -> str:
    return format_admin_success(await get_direct_telegram_webhook_info())


async def handle_admin_tool_command(db: AsyncSession, admin: User, clean: str) -> str | None:
    command = clean.split(maxsplit=1)[0].lower()
    if command.startswith("/") and "@" in command:
        command = command.split("@", maxsplit=1)[0]
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
    if command == "/setlifecycle":
        return await setlifecycle_command(db, clean)
    if command == "/close":
        return await close_sessions_command(db, clean)
    if command == "/shoplink":
        return await shoplink_command(db, clean)
    if command == "/withdrawals":
        return await withdrawals_command(db)
    if command == "/withdrawdone":
        return await withdrawdone_command(db, clean)
    if command == "/synccommands":
        result = await sync_telegram_bot_commands()
        if result.startswith("Меню команд Telegram обновлено."):
            return format_admin_success(result)
        return format_admin_error(result)
    if command == "/syncwebhook":
        return await syncwebhook_command()
    if command == "/webhookinfo":
        return await webhookinfo_command()
    return None
