import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.message import MessageResponse
from app.schemas.user import UserCreate
from app.services.dialogue import (
    add_message,
    first_contact_intro_animation,
    get_active_session,
    handle_user_text,
)
from app.services.stars import answer_pre_checkout_query, process_successful_star_payment
from app.services.telegram_delivery import answer_callback_query, send_telegram_response
from app.services.users import get_or_create_user

router = APIRouter()
logger = logging.getLogger(__name__)


async def build_telegram_response(update: dict[str, Any], db: AsyncSession) -> MessageResponse:
    pre_checkout_query = update.get("pre_checkout_query") or {}
    if pre_checkout_query:
        sender = pre_checkout_query.get("from") or {}
        telegram_id = sender.get("id")
        if telegram_id is None:
            raise HTTPException(status_code=400, detail="Pre-checkout query without sender")
        user = await get_or_create_user(
            db,
            UserCreate(
                telegram_id=int(telegram_id),
                username=sender.get("username"),
                first_name=sender.get("first_name"),
            ),
        )
        session = await get_active_session(db, user, source="telegram")
        ok, error = await answer_pre_checkout_query(
            db,
            pre_checkout_query=pre_checkout_query,
        )
        await add_message(
            db,
            user=user,
            session=session,
            role="user",
            content=f"stars_pre_checkout:{pre_checkout_query.get('invoice_payload')}",
            metadata={
                "telegram_update_id": update.get("update_id"),
                "pre_checkout_query_id": pre_checkout_query.get("id"),
            },
        )
        await db.commit()
        return MessageResponse(
            user_id=user.id,
            session_id=session.id,
            reply=reply,
            mode=mode,
            token_delta=token_delta,
            subjectivity_score=user.subjectivity_score,
            reply_markup=reply_markup,
            intro_animation=first_contact_intro_animation()
            if mode == "onboarding_start"
            else None,
            loading_message=(
                "```markdown\nВаши ответы анализируются...\n\nОракул оценивает уровень субъектности.\n```"
                if mode == "onboarding_complete"
                else None
            ),
        )

    callback_query = update.get("callback_query") or {}
    message = update.get("message") or callback_query.get("message") or {}
    chat = message.get("chat") or {}
    sender = callback_query.get("from") or message.get("from") or chat
    text = callback_query.get("data") or message.get("text")
    telegram_id = sender.get("id")
    chat_id = chat.get("id")

    if telegram_id is None:
        raise HTTPException(
            status_code=400,
            detail="Telegram sender is missing",
        )

    user = await get_or_create_user(
        db,
        UserCreate(
            telegram_id=int(telegram_id),
            username=sender.get("username"),
            first_name=sender.get("first_name"),
        ),
    )
    session = await get_active_session(db, user, source="telegram")

    successful_payment = message.get("successful_payment") or {}
    if successful_payment:
        await add_message(
            db,
            user=user,
            session=session,
            role="user",
            content=f"stars_successful_payment:{successful_payment.get('invoice_payload')}",
            metadata={
                "telegram_update_id": update.get("update_id"),
                "chat_id": chat_id,
                "chat_type": chat.get("type"),
                "successful_payment": successful_payment,
            },
        )
        reply = await process_successful_star_payment(
            db,
            user=user,
            successful_payment=successful_payment,
        )
        await add_message(db, user=user, session=session, role="assistant", content=reply)
        await db.commit()
        return MessageResponse(
            user_id=user.id,
            session_id=session.id,
            reply=reply,
            mode="stars_successful_payment",
            subjectivity_score=user.subjectivity_score,
        )

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Only text messages, payments and callback buttons are supported",
        )
    await add_message(
        db,
        user=user,
        session=session,
        role="user",
        content=text,
        metadata={
            "telegram_update_id": update.get("update_id"),
            "chat_id": chat_id,
            "chat_type": chat.get("type"),
            "callback_query_id": callback_query.get("id"),
            "callback_data": callback_query.get("data"),
        },
    )

    reply, mode, token_delta, reply_markup = await handle_user_text(
        db,
        user=user,
        session=session,
        text=text,
        chat_id=int(chat_id) if chat_id is not None else None,
        chat_type=chat.get("type"),
    )
    await add_message(db, user=user, session=session, role="assistant", content=reply)
    await db.commit()

    return MessageResponse(
        user_id=user.id,
        session_id=session.id,
        reply=reply,
        mode=mode,
        token_delta=token_delta,
        subjectivity_score=user.subjectivity_score,
        reply_markup=reply_markup,
        intro_animation=first_contact_intro_animation()
        if mode == "onboarding_start"
        else None,
    )


async def process_direct_telegram_update(update: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await answer_callback_query(update)
            response = await build_telegram_response(update, db)
            await send_telegram_response(update, response, answer_callback=False)
        except Exception:
            await db.rollback()
            logger.exception("Failed to process direct Telegram update")
            raise


@router.post("/webhook", response_model=MessageResponse)
async def telegram_webhook(
    update: dict[str, Any], db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    return await build_telegram_response(update, db)


@router.post("/direct-webhook")
async def telegram_direct_webhook(
    update: dict[str, Any],
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, bool]:
    secret = settings.telegram_webhook_secret_token.strip()
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    background_tasks.add_task(process_direct_telegram_update, update)
    return {"ok": True}
