from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.message import MessageResponse
from app.schemas.user import UserCreate
from app.services.dialogue import add_message, get_active_session, handle_user_text
from app.services.users import get_or_create_user

router = APIRouter()


@router.post("/webhook", response_model=MessageResponse)
async def telegram_webhook(update: dict[str, Any], db: AsyncSession = Depends(get_db)) -> MessageResponse:
    callback_query = update.get("callback_query") or {}
    message = update.get("message") or callback_query.get("message") or {}
    chat = message.get("chat") or {}
    sender = callback_query.get("from") or message.get("from") or chat
    text = callback_query.get("data") or message.get("text")
    telegram_id = sender.get("id")
    chat_id = chat.get("id")

    if telegram_id is None or not text:
        raise HTTPException(
            status_code=400,
            detail="Only text messages and callback buttons are supported in MVP",
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
    )
