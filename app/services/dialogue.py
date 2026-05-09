from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.message import Message
from app.models.news import NewsItem
from app.models.session import ConversationSession
from app.models.user import User
from app.services.assessment import create_assessment
from app.services.admins import is_admin
from app.services.battles import create_battle_placeholder
from app.services.cases import get_random_case
from app.core.config import settings
from app.services.llm import SUPPORT_SYSTEM_PROMPT, openrouter_chat
from app.services.marketplace import buy_item, format_shop
from app.services.news import get_or_create_news_case
from app.services.summaries import create_due_summaries


async def get_active_session(db: AsyncSession, user: User, source: str = "telegram") -> ConversationSession:
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
        return "Я рядом. Напишите, что сейчас с вами происходит, и мы аккуратно разберем это вместе."

    return (
        "Я услышал вас. Похоже, сейчас важно не торопиться с выводами, а чуть бережнее "
        "присмотреться к тому, что именно вы чувствуете и чего вам сейчас не хватает.\n\n"
        "Если попробовать назвать это одним словом, что ближе: усталость, тревога, злость, "
        "растерянность или что-то другое?"
    )


async def build_supportive_reply_with_context(
    db: AsyncSession,
    *,
    session: ConversationSession,
    text: str,
) -> str:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at.desc())
        .limit(12)
    )
    recent = list(reversed(result.scalars().all()))
    messages = [{"role": "system", "content": SUPPORT_SYSTEM_PROMPT}]
    for message in recent:
        if message.role in {"user", "assistant"}:
            messages.append({"role": message.role, "content": message.content})
    messages.append({"role": "user", "content": text})

    try:
        return await openrouter_chat(messages, temperature=0.7, max_tokens=550)
    except Exception:
        return build_supportive_reply(text)


def format_case(case: Case) -> str:
    return (
        "Испытание Оракула ИИ\n\n"
        f"{case.title}\n\n"
        f"{case.prompt}\n\n"
        "Ответьте свободно: что вы сделаете, почему именно так, и что в этой ситуации "
        "для вас будет самым трудным?"
    )


def format_profile(user: User) -> str:
    status_labels = {
        "object": "Объект",
        "seeker": "Соискатель",
        "faithful": "Верный",
        "keeper": "Хранитель",
        "sighted": "Зрячий",
        "subject": "Субъект",
    }
    return (
        "Ваш профиль Оракула ИИ\n\n"
        f"Статус: {status_labels.get(user.status, user.status)}\n"
        f"Индекс рефлексии: {user.subjectivity_score}/100\n"
        f"Токены: {user.token_balance}\n\n"
        f"{user.profile_summary or 'Профиль пока пустой. Пройдите /case, чтобы появилась первая оценка.'}"
    )


def format_help() -> str:
    return (
        "Я — Оракул ИИ.\n\n"
        "В обычном режиме я остаюсь поддерживающим психологическим помощником: можно писать о "
        "состоянии, тревоге, сложном выборе или отношениях.\n\n"
        "Команды:\n"
        "/case — пройти короткий этический кейс и получить оценку с токенами\n"
        "/news — Sentinel Mode: новостной этический кейс\n"
        "/battle — создать заготовку баттла\n"
        "/shop — витрина collectibles за токены\n"
        "/profile — посмотреть профиль и баланс\n"
        "/help — показать это меню"
    )


async def handle_user_text(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession,
    text: str,
    chat_id: int | None = None,
    chat_type: str | None = None,
) -> tuple[str, str, int]:
    clean = text.strip()
    command = clean.split(maxsplit=1)[0].lower()

    if command == "/start":
        return (
            "Доброго дня! Я — Оракул ИИ.\n\n"
            "В обычном режиме я буду поддерживающим психологическим помощником. "
            "Если захотите пройти испытание с оценкой и токенами, отправьте /case.\n\n"
            "Как вы себя чувствуете сегодня?",
            "start",
            0,
        )
    if command == "/help":
        return format_help(), "help", 0
    if command in {"/profile", "/status"}:
        return format_profile(user), "profile", 0
    if command in {"/summary", "/summaries"}:
        if not is_admin(user):
            return "Эта команда доступна только администратору.", "forbidden", 0
        summaries = await create_due_summaries(db, older_than_minutes=60)
        if not summaries:
            return "Новых завершенных бесед для summary пока нет.", "admin_summary_empty", 0
        return (
            "Созданы новые summary:\n\n"
            + "\n\n".join(f"@{s.username or 'без username'}\n{s.text[:1200]}" for s in summaries[:5]),
            "admin_summary",
            0,
        )
    if command == "/case":
        case = await get_random_case(db)
        session.state = f"case:{case.id}"
        return format_case(case), "case_prompt", 0
    if command == "/news":
        item = await get_or_create_news_case(db)
        session.state = f"news:{item.id}"
        return (
            "Sentinel Mode\n\n"
            f"{item.ethical_case}\n\n"
            "Займите позицию: что здесь требует ответственности, где возможна манипуляция, "
            "и какой выбор сохранит достоинство?",
            "news_prompt",
            0,
        )
    if command == "/battle":
        topic = clean.split(maxsplit=1)[1] if len(clean.split(maxsplit=1)) > 1 else None
        battle = await create_battle_placeholder(db, user=user, chat_id=chat_id, topic=topic)
        location = "группе" if chat_type in {"group", "supergroup"} else "личном чате"
        return (
            "Баттл создан как заготовка.\n\n"
            f"ID: {battle.id}\n"
            f"Режим: {location}\n\n"
            "Сейчас это подготовительный слой: база уже хранит баттлы и участников. "
            "Следующим шагом добавим присоединение второго участника, таймеры, стороны "
            "и финальный разбор.",
            "battle_placeholder",
            0,
        )
    if command == "/shop":
        return (
            await format_shop(db)
            + "\n\nВеб-витрина для теста: "
            + settings.public_webapp_url
            + f"?telegram_id={user.telegram_id}",
            "shop",
            0,
        )
    if command == "/buy":
        parts = clean.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            return "Напишите номер предмета, например: /buy 1", "buy_help", 0
        return await buy_item(db, user, int(parts[1].strip())), "buy", 0

    if session.state.startswith("case:"):
        case_id = session.state.removeprefix("case:")
        result = await db.execute(select(Case).where(Case.id == UUID(case_id)))
        case = result.scalar_one_or_none()
        session.state = "active"
        if case is None:
            return (
                "Кейс не найден, поэтому я вернул вас в обычный режим. Можно начать новый: /case",
                "case_missing",
                0,
            )
        assessment, token_delta = await create_assessment(
            db,
            user=user,
            text=clean,
            source="case_answer",
            case_id=case.id,
            session_id=session.id,
            case_prompt=case.prompt,
        )
        reply = (
            "Разбор Оракула ИИ\n\n"
            f"Субъектность: {assessment.subjectivity}/100\n"
            f"Честность: {assessment.honesty}/100\n"
            f"Эмоциональная устойчивость: {assessment.emotional_sovereignty}/100\n"
            f"Когнитивное смирение: {assessment.cognitive_humility}/100\n"
            f"Эмпатия: {assessment.empathy}/100\n\n"
            f"{assessment.summary}\n\n"
            f"Начислено токенов: {token_delta}\n"
            "Чтобы пройти еще один кейс, отправьте /case. Чтобы вернуться к разговору, просто напишите сообщение."
        )
        return reply, "case_assessment", token_delta

    if session.state.startswith("news:"):
        news_id = session.state.removeprefix("news:")
        result = await db.execute(select(NewsItem).where(NewsItem.id == UUID(news_id)))
        item = result.scalar_one_or_none()
        session.state = "active"
        if item is None:
            return "Новостной кейс не найден. Можно начать новый: /news", "news_missing", 0
        assessment, token_delta = await create_assessment(
            db,
            user=user,
            text=clean,
            source="news_sentinel",
            session_id=session.id,
            case_prompt=item.ethical_case,
        )
        reply = (
            "Разбор Sentinel Mode\n\n"
            f"Субъектность: {assessment.subjectivity}/100\n"
            f"Честность: {assessment.honesty}/100\n"
            f"Эмоциональная устойчивость: {assessment.emotional_sovereignty}/100\n"
            f"Когнитивное смирение: {assessment.cognitive_humility}/100\n"
            f"Эмпатия: {assessment.empathy}/100\n\n"
            f"{assessment.summary}\n\n"
            f"Начислено токенов: {token_delta}"
        )
        return reply, "news_assessment", token_delta

    reply = await build_supportive_reply_with_context(db, session=session, text=clean)
    await create_assessment(
        db,
        user=user,
        text=clean,
        source="support_signal",
        session_id=session.id,
        use_llm=False,
        award_tokens=False,
    )
    return reply, "support", 0
