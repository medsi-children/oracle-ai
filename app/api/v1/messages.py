from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.user import UserCreate
from app.services.dialogue import add_message, get_active_session, handle_user_text
from app.services.users import get_or_create_user

router = APIRouter()


@router.post("", response_model=MessageResponse)
async def create_message(payload: MessageCreate, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    user = await get_or_create_user(
        db,
        UserCreate(
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
        ),
    )
    session = await get_active_session(db, user, source=payload.source)
    await add_message(db, user=user, session=session, role="user", content=payload.text)

    reply, mode, token_delta = await handle_user_text(
        db,
        user=user,
        session=session,
        text=payload.text,
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
    )
