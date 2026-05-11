from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.stars import StarPaymentOrder, StarWithdrawalRequest
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.admins import admin_ids
from app.services.assessment import calculate_status

DEFAULT_CLOSED_GROUP_INVITE_URL = "https://t.me/+jkSp6Vx8L35kYmRi"


class TelegramStarsError(RuntimeError):
    pass


def display_user(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    if user.telegram_id is not None:
        return f"id {user.telegram_id}"
    return str(user.id)


async def telegram_api(method: str, payload: dict) -> dict:
    token = settings.telegram_bot_token.strip()
    if not token:
        raise TelegramStarsError("TELEGRAM_BOT_TOKEN не задан.")

    async with httpx.AsyncClient(timeout=14) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload,
        )
    data = response.json()
    if response.status_code >= 400 or not data.get("ok"):
        raise TelegramStarsError(data.get("description") or response.text)
    return data


async def notify_admins(text: str) -> None:
    ids = admin_ids()
    if not ids:
        return
    for admin_id in ids:
        try:
            await telegram_api(
                "sendMessage",
                {
                    "chat_id": admin_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
            )
        except TelegramStarsError:
            continue


async def create_star_invoice_link(
    db: AsyncSession,
    *,
    user: User,
    order_type: str,
    star_amount: int,
    token_amount: int,
    title: str,
    description: str,
) -> tuple[StarPaymentOrder, str]:
    if star_amount <= 0:
        raise TelegramStarsError("Количество звезд должно быть больше нуля.")
    payload = f"ethos:{order_type}:{user.id}:{uuid4().hex}"
    order = StarPaymentOrder(
        user_id=user.id,
        order_type=order_type,
        status="pending",
        star_amount=star_amount,
        token_amount=token_amount,
        invoice_payload=payload,
        note=description,
    )
    db.add(order)
    await db.flush()

    try:
        data = await telegram_api(
            "createInvoiceLink",
            {
                "title": title[:32],
                "description": description[:255],
                "payload": payload,
                "provider_token": "",
                "currency": "XTR",
                "prices": [{"label": title[:32], "amount": star_amount}],
            },
        )
    except TelegramStarsError as exc:
        order.status = "failed"
        order.note = f"{description}\n\nОшибка Telegram: {exc}"
        await db.flush()
        raise

    return order, str(data["result"])


async def answer_pre_checkout_query(
    db: AsyncSession,
    *,
    pre_checkout_query: dict,
) -> tuple[bool, str]:
    query_id = pre_checkout_query.get("id")
    payload = pre_checkout_query.get("invoice_payload")
    currency = pre_checkout_query.get("currency")
    total_amount = int(pre_checkout_query.get("total_amount") or 0)

    ok = False
    error = "Платеж не найден. Откройте счет заново."
    if query_id and payload and currency == "XTR":
        result = await db.execute(
            select(StarPaymentOrder).where(
                StarPaymentOrder.invoice_payload == payload,
                StarPaymentOrder.status == "pending",
            )
        )
        order = result.scalar_one_or_none()
        if order is not None and order.star_amount == total_amount:
            ok = True
            error = ""

    await telegram_api(
        "answerPreCheckoutQuery",
        {
            "pre_checkout_query_id": query_id,
            "ok": ok,
            **({} if ok else {"error_message": error}),
        },
    )
    return ok, error


async def process_successful_star_payment(
    db: AsyncSession,
    *,
    user: User,
    successful_payment: dict,
) -> str:
    payload = successful_payment.get("invoice_payload")
    currency = successful_payment.get("currency")
    total_amount = int(successful_payment.get("total_amount") or 0)
    charge_id = successful_payment.get("telegram_payment_charge_id")

    if currency != "XTR" or not payload:
        return "Оплата получена, но это не платеж звездами. Напишите администратору."

    result = await db.execute(
        select(StarPaymentOrder).where(StarPaymentOrder.invoice_payload == payload)
    )
    order = result.scalar_one_or_none()
    if order is None:
        await notify_admins(
            "Получен платеж звездами без найденного заказа.\n\n"
            f"Пользователь: {display_user(user)}\n"
            f"Звезды: {total_amount}\n"
            f"payload: {payload}"
        )
        return "Оплата получена, но заказ не найден. Администратор уже получил сигнал."

    if order.status == "paid":
        return _paid_message(user, order)

    if order.user_id != user.id or order.star_amount != total_amount:
        order.status = "failed"
        order.note = (order.note or "") + "\n\nПлатеж не совпал с пользователем или суммой."
        await notify_admins(
            "Платеж звездами требует ручной проверки.\n\n"
            f"Пользователь: {display_user(user)}\n"
            f"Order: {order.id}\n"
            f"Звезды: {total_amount}"
        )
        return "Оплата требует ручной проверки. Администратор уже получил сигнал."

    order.status = "paid"
    order.telegram_payment_charge_id = charge_id

    if order.order_type == "psycoin_topup":
        user.token_balance += order.token_amount
        user.status = calculate_status(user.subjectivity_score, user.token_balance)
        db.add(
            TokenLedgerEntry(
                user_id=user.id,
                amount=order.token_amount,
                reason=f"Telegram Stars top-up: {order.star_amount} XTR",
            )
        )
    elif order.order_type == "system_entry":
        user.lifecycle_status = "follower"

    await db.flush()
    await notify_admins(
        "Платеж звездами прошел успешно.\n\n"
        f"Пользователь: {display_user(user)}\n"
        f"Тип: {order.order_type}\n"
        f"Звезды: {order.star_amount}\n"
        f"Псикоины: {order.token_amount}"
    )
    return _paid_message(user, order)


def _paid_message(user: User, order: StarPaymentOrder) -> str:
    if order.order_type == "system_entry":
        invite_url = settings.closed_group_invite_url or DEFAULT_CLOSED_GROUP_INVITE_URL
        return (
            "Вход в систему ETHOS подтвержден.\n\n"
            "Закрытый чат уже доступен по ссылке:\n"
            f"{invite_url}"
        )
    if order.order_type == "psycoin_topup":
        return (
            "Псикоины зачислены.\n\n"
            f"+{order.token_amount} за {order.star_amount} ⭐\n"
            f"Текущий баланс: {user.token_balance}."
        )
    return "Оплата звездами получена."


async def create_withdrawal_request(
    db: AsyncSession,
    *,
    user: User,
    token_amount: int,
) -> StarWithdrawalRequest:
    token_amount = max(settings.psycoin_withdraw_min, token_amount)
    rate = max(1, settings.psycoin_per_star)
    if token_amount % rate:
        token_amount = token_amount - (token_amount % rate)
    star_amount = token_amount // rate
    if token_amount < settings.psycoin_withdraw_min:
        raise TelegramStarsError(
            f"Минимальный вывод: {settings.psycoin_withdraw_min} псикоинов."
        )
    if user.token_balance < token_amount:
        raise TelegramStarsError(
            f"Недостаточно псикоинов. Нужно {token_amount}, сейчас {user.token_balance}."
        )

    existing_result = await db.execute(
        select(StarWithdrawalRequest)
        .where(
            StarWithdrawalRequest.user_id == user.id,
            StarWithdrawalRequest.status == "pending",
        )
        .limit(1)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise TelegramStarsError(
            "У вас уже есть активная заявка на вывод. Дождитесь ручной обработки администратором."
        )

    user.token_balance -= token_amount
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    request = StarWithdrawalRequest(
        user_id=user.id,
        status="pending",
        token_amount=token_amount,
        star_amount=star_amount,
        admin_note="Заявка создана пользователем в mini-app.",
    )
    db.add(request)
    db.add(
        TokenLedgerEntry(
            user_id=user.id,
            amount=-token_amount,
            reason=f"Telegram Stars withdrawal request: {star_amount} XTR",
        )
    )
    await db.flush()
    await notify_admins(
        "Новая заявка на вывод псикоинов в звезды.\n\n"
        f"Заявка: {request.id}\n"
        f"Пользователь: {display_user(user)}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"К выводу: {token_amount} псикоинов = {star_amount} ⭐\n\n"
        f"После ручной выплаты отметьте: /withdrawdone {request.id}"
    )
    return request


async def list_pending_withdrawals(db: AsyncSession, *, limit: int = 10) -> list[tuple[StarWithdrawalRequest, User]]:
    result = await db.execute(
        select(StarWithdrawalRequest, User)
        .join(User, User.id == StarWithdrawalRequest.user_id)
        .where(StarWithdrawalRequest.status == "pending")
        .order_by(StarWithdrawalRequest.created_at.asc())
        .limit(limit)
    )
    return list(result.all())


async def mark_withdrawal_done(db: AsyncSession, request_id: str) -> StarWithdrawalRequest | None:
    result = await db.execute(
        select(StarWithdrawalRequest).where(StarWithdrawalRequest.status == "pending")
    )
    requests = list(result.scalars().all())
    request = next(
        (candidate for candidate in requests if str(candidate.id).startswith(request_id)),
        None,
    )
    if request is None:
        return None
    request.status = "fulfilled"
    request.fulfilled_at = datetime.now(UTC)
    await db.flush()
    return request
