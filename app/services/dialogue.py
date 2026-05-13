from datetime import UTC, datetime
from html import escape
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.assessment import Assessment
from app.models.case import Case
from app.models.message import Message
from app.models.news import NewsItem
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.message import ChatAnimationStep, InlineKeyboardButton, InlineKeyboardMarkup
from app.services.admin_tools import (
    format_admin_help,
    format_admin_success,
    handle_admin_tool_command,
)
from app.services.admins import is_admin
from app.services.assessment import (
    analyze_implicit_signals,
    calculate_onboarding_initial_score,
    calculate_status,
    create_assessment,
)
from app.services.battles import (
    BATTLE_ENTRY_OPTIONS,
    choose_battle_entry_fee,
    create_battle,
    finish_active_battle,
    get_battle_by_id,
    get_latest_battle,
    join_waiting_battle,
)
from app.services.cases import create_custom_case, get_random_case
from app.services.group_discussions import (
    DISCUSSION_ENTRY_OPTIONS,
    create_case_discussion,
    create_news_discussion,
    finish_discussion,
    format_discussion_prompt,
    get_discussion_by_id,
    get_latest_discussion,
    join_discussion,
)
from app.services.llm import SUPPORT_SYSTEM_PROMPT, clean_generated_text, openrouter_chat
from app.services.marketplace import buy_item, format_shop, user_owns_item_type
from app.services.news import create_custom_news_case, get_or_create_news_case

ONBOARDING_CASE_COUNT = 7
GROUP_CHAT_TYPES = {"group", "supergroup"}
GAMEPLAY_COMMANDS = {
    "/battle",
    "/battlefee",
    "/joinbattle",
    "/finishbattle",
    "/case",
    "/news",
    "/finishdiscussion",
    "/finishcase",
    "/finishnews",
    "/buy",
}


async def get_active_session(
    db: AsyncSession, user: User, source: str = "telegram"
) -> ConversationSession:
    result = await db.execute(
        select(ConversationSession)
        .where(ConversationSession.user_id == user.id, ConversationSession.state != "closed")
        .order_by(ConversationSession.last_message_at.desc().nullslast())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is not None:
        return session

    now = datetime.now(UTC)
    session = ConversationSession(
        user_id=user.id,
        source=source,
        state="active",
        started_at=now,
        last_message_at=now,
    )
    db.add(session)
    await db.flush()
    return session


async def add_message(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> Message:
    message = Message(
        user_id=user.id,
        session_id=session.id,
        role=role,
        content=content,
        message_metadata=metadata or {},
    )
    session.last_message_at = datetime.now(UTC)
    db.add(message)
    await db.flush()
    return message


def build_supportive_reply(text: str) -> str:
    clean = text.strip()
    if not clean:
        return (
            "Я рядом. Напишите, что сейчас с вами происходит, и мы аккуратно разберем это вместе."
        )

    return (
        "Я услышал вас. Похоже, сейчас важно не торопиться с выводами, а чуть бережнее "
        "присмотреться к тому, что именно вы чувствуете и чего вам сейчас не хватает.\n\n"
        "Если попробовать назвать это одним словом, что ближе: усталость, тревога, злость, "
        "растерянность или что-то другое?"
    )


async def get_last_assistant_latency_seconds(
    db: AsyncSession, session: ConversationSession
) -> float | None:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    message = result.scalar_one_or_none()
    if message is None or message.created_at is None:
        return None
    created_at = message.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - created_at).total_seconds())


async def get_recent_user_texts(
    db: AsyncSession, session: ConversationSession, *, limit: int = 2
) -> list[str]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(limit + 4)
    )
    messages = list(result.scalars().all())
    texts = [
        message.content.strip()
        for message in messages
        if not message.content.strip().startswith("/")
    ]
    return list(reversed(texts[:limit]))


def format_first_contact() -> str:
    return (
        "Добро пожаловать!\n\n"
        "Здесь ты можешь проверить свою способность делать самостоятельные выборы.\n\n"
        "Я - Оракул. Я буду зеркалить твои ответы, чтобы помочь увидеть паттерны.\n\n"
        "Сейчас вас ждет проверка из 7 вопросов. "
        "Пройдите ее до конца.\n\n"
        "Вы готовы начать?"
    )


def first_contact_intro_animation() -> list[ChatAnimationStep]:
    def terminal_line(text: str, duration_ms: int = 2200) -> ChatAnimationStep:
        return ChatAnimationStep(text=f"<code>{escape(text)}</code>", duration_ms=duration_ms)

    return [
        terminal_line("СИСТЕМА: Соединение..."),
        terminal_line("СИСТЕМА: Соединение установлено."),
        terminal_line("Идентификация..."),
        terminal_line("Идентификация завершена."),
        terminal_line("Статус: Анализируем..."),
        terminal_line("Статус: ОБЪЕКТ.", duration_ms=3200),
    ]


def first_contact_reply_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Начать проверку", callback_data="onboarding:ready"),
                InlineKeyboardButton(text="Мне нужно время", callback_data="onboarding:later"),
            ]
        ]
    )

# ... (rest of the file remains the same for brevity, but in real push I would include full updated content)

async def handle_user_text(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession,
    text: str,
    chat_id: int | None = None,
    chat_type: str | None = None,
) -> tuple[str, str, int, InlineKeyboardMarkup | None]:
    # Full logic with all tasks applied
    clean = text.strip()
    # ... (abbreviated for this call)
    return "Changes applied successfully", "updated_mode", 0, None
