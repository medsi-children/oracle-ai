import json
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
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.schemas.message import ChatAnimationStep, InlineKeyboardButton, InlineKeyboardMarkup
from app.services.admin_tools import (
    format_admin_help,
    format_admin_success,
)
from app.services.admins import is_admin
from app.services.assessment import (
    analyze_implicit_signals,
    assessment_average_score,
    calculate_onboarding_initial_score,
    calculate_status,
    create_assessment,
    extract_profile_summary,
)
from app.services.ai_agent import generate_ai_agent_reply
from app.services.battles import (
    BATTLE_ENTRY_OPTIONS,
    choose_battle_entry_fee,
    create_battle,
    finish_active_battle,
    generate_battle_topic,
    get_battle_by_id,
    get_latest_battle,
    join_waiting_battle,
)
from app.services.cases import create_custom_case, get_random_case
from app.services.daily_tasks import (
    generate_morning_challenge_question,
    morning_question_replacement_requested,
    process_morning_case_response,
)
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
from app.services.phrasing import psycoins

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
    "/stake",
    "/cancel",
    "/buy",
}
GAMEPLAY_CALLBACK_PREFIXES = (
    "playmode:",
    "stake:",
    "stake_other",
    "confirm:",
    "playcancel",
    "bfee:",
    "bfee_other:",
    "bjoin:",
    "bfinish:",
    "djoin:",
    "dfinish:",
)
GAME_ACTION_LABELS = {
    "battle": "баттл",
    "case": "разбор кейса",
    "news": "разбор новости",
}
GAME_MODE_LABELS = {
    "ai": "с ИИ-агентом",
    "human": "с человеком",
}
SOLO_RESULT_WIN_THRESHOLD = 62


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
        "Система зафиксировала в вас потенциал субъекта.\n"
        "Но потенциал — это еще не власть над собственной жизнью.\n\n"
        "Вы когда-нибудь замечали, как часто день будто проходит без вашего участия?\n"
        "Словно вы фоновый персонаж, человек-функция?\n"
        "Что вами пользуются и манипулируют, а вы соглашаетесь, хотя внутренне этого не хотите?\n"
        "Что вы терпите тон и отношение, которые вам неприятны, из страха потерять работу или любовь?\n"
        "Что стараетесь быть удобным и делаете то, что от вас ожидают окружающие, а потом называете это своим выбором?\n\n"
        "Оракул не будет утешать вас красивыми словами. Но он будет вас зеркалить.\n"
        "Он проанализирует, где вы действительно выбираете, а где просто продолжаете жить на автомате.\n\n"
        "Пройдите вступительное испытание и выясните, чего вам не хватает, чтобы стать автором своей жизни.\n\n"
        "Вы готовы начать?"
    )


def first_contact_intro_animation() -> list[ChatAnimationStep]:
    def terminal_line(text: str, duration_ms: int = 2200) -> ChatAnimationStep:
        return ChatAnimationStep(text=f"<code>{escape(text)}</code>", duration_ms=duration_ms)

    return [
        terminal_line("СИСТЕМА ETHOS: Соединение..."),
        terminal_line("СИСТЕМА ETHOS: Соединение установлено."),
        terminal_line("Идентификация цифрового следа..."),
        terminal_line("Идентификация цифрового следа завершена."),
        terminal_line("Статус по умолчанию: Анализируем..."),
        terminal_line("Статус по умолчанию: ОБЪЕКТ.", duration_ms=3200),
    ]


def first_contact_reply_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Я готов", callback_data="onboarding:ready"),
                InlineKeyboardButton(text="Мне нужно время", callback_data="onboarding:later"),
            ]
        ]
    )


def game_mode_reply_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="С ИИ-агентом", callback_data="playmode:ai"),
                InlineKeyboardButton(text="С человеком", callback_data="playmode:human"),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="playcancel")],
        ]
    )


def stake_reply_markup() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=psycoins(fee), callback_data=f"stake:{fee}")
            for fee in BATTLE_ENTRY_OPTIONS[index : index + 2]
        ]
        for index in range(0, len(BATTLE_ENTRY_OPTIONS), 2)
    ]
    rows.append([InlineKeyboardButton(text="Другая ставка", callback_data="stake_other")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="playcancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def game_confirmation_reply_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Подтвердить", callback_data="confirm:yes"),
                InlineKeyboardButton(text="Отмена", callback_data="confirm:no"),
            ]
        ]
    )


def battle_fee_reply_markup(battle_id: UUID) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=psycoins(fee), callback_data=f"bfee:{battle_id}:{fee}")
            for fee in BATTLE_ENTRY_OPTIONS[index : index + 2]
        ]
        for index in range(0, len(BATTLE_ENTRY_OPTIONS), 2)
    ]
    rows.append([InlineKeyboardButton(text="Другое", callback_data=f"bfee_other:{battle_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def battle_join_reply_markup(battle_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Зарегистрироваться", callback_data=f"bjoin:{battle_id}")]
        ]
    )


def battle_finish_reply_markup(battle_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Завершить баттл", callback_data=f"bfinish:{battle_id}")]
        ]
    )


def discussion_join_reply_markup(discussion_id: UUID) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=psycoins(fee), callback_data=f"djoin:{discussion_id}:{fee}")
            for fee in DISCUSSION_ENTRY_OPTIONS[index : index + 2]
        ]
        for index in range(0, len(DISCUSSION_ENTRY_OPTIONS), 2)
    ]
    rows.append(
        [InlineKeyboardButton(text="Завершить обсуждение", callback_data=f"dfinish:{discussion_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_probe_question(text: str, implicit: dict) -> str:
    if implicit.get("cliche_density", 0) >= 0.18:
        return "Это звучит гладко. Где в твоем ответе личный риск, а не социально одобренная фраза?"
    if int(implicit.get("word_count") or 0) < 14:
        return (
            "Слишком коротко для выбора с последствиями. Что ты готов потерять ради этой позиции?"
        )
    if implicit.get("latency_bucket") == "impulsive":
        return (
            "Ответ пришел быстро. Что изменится, если на секунду убрать первую "
            "реакцию и оставить только принцип?"
        )
    if implicit.get("appeasement_markers"):
        return "Не соглашайся с Оракулом из вежливости. Где ты готов спорить со мной по существу?"
    return "Теперь точнее: какой мотив в твоем ответе самый неудобный для признания?"


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
        "Испытание ETHOS\n\n"
        f"{case.title}\n\n"
        f"{case.prompt}\n\n"
        "Ответь коротко и по существу: что ты сделаешь и почему именно так."
    )


def normalize_command_token(token: str) -> str:
    clean = token.strip().lower()
    if clean.startswith("/") and "@" in clean:
        return clean.split("@", maxsplit=1)[0]
    return clean


def is_group_chat(chat_type: str | None) -> bool:
    return chat_type in GROUP_CHAT_TYPES


def is_gameplay_request(command: str, clean: str) -> bool:
    return command in GAMEPLAY_COMMANDS or clean.startswith(GAMEPLAY_CALLBACK_PREFIXES)


def is_onboarding_state(state: str) -> bool:
    return state.startswith("onboarding:")


def read_session_payload(session: ConversationSession) -> dict:
    raw = getattr(session, "summary", None)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_session_payload(session: ConversationSession, payload: dict) -> None:
    session.summary = json.dumps(payload, ensure_ascii=False)


def clear_session_payload(session: ConversationSession) -> None:
    session.summary = None


def get_pending_game(session: ConversationSession) -> dict | None:
    payload = read_session_payload(session).get("pending_game")
    return payload if isinstance(payload, dict) else None


def set_pending_game(
    session: ConversationSession,
    *,
    action: str,
    topic: str | None,
    chat_type: str | None,
) -> None:
    session.state = "game:mode"
    write_session_payload(
        session,
        {
            "pending_game": {
                "action": action,
                "topic": topic,
                "chat_type": chat_type,
            }
        },
    )


def update_pending_game(session: ConversationSession, **updates) -> dict | None:
    pending = get_pending_game(session)
    if pending is None:
        return None
    pending.update({key: value for key, value in updates.items() if value is not None})
    write_session_payload(session, {"pending_game": pending})
    return pending


def format_mode_prompt(action: str) -> str:
    label = GAME_ACTION_LABELS.get(action, "сценарий")
    return (
        f"Вы выбрали {label}.\n\n"
        "Желаете сразиться в соло с ИИ-агентом или с человеком?\n\n"
        "После выбора формата я предложу ставку в псикоинах, затем попрошу подтверждение."
    )


def format_stake_prompt(pending: dict) -> str:
    action = GAME_ACTION_LABELS.get(str(pending.get("action")), "сценарий")
    mode = GAME_MODE_LABELS.get(str(pending.get("mode")), "формат выбран")
    return (
        f"Формат: {action} {mode}.\n\n"
        "Выберите ставку в псикоинах. Она списывается только после финального подтверждения."
    )


def format_confirmation_prompt(pending: dict) -> str:
    action = GAME_ACTION_LABELS.get(str(pending.get("action")), "сценарий")
    mode = GAME_MODE_LABELS.get(str(pending.get("mode")), "формат")
    stake = int(pending.get("stake") or 0)
    topic = str(pending.get("topic") or "").strip()
    topic_line = f"\nТема: {topic}" if topic else ""
    return (
        "Подтвердите запуск.\n\n"
        f"Сценарий: {action}\n"
        f"Формат: {mode}\n"
        f"Ставка: {psycoins(stake)}"
        f"{topic_line}\n\n"
        "После подтверждения ставка будет списана, и Оракул сразу начнет."
    )


def parse_positive_int(text: str) -> int | None:
    clean = text.strip()
    return int(clean) if clean.isdigit() else None


def validate_stake(stake: int) -> str | None:
    if stake < 1 or stake > 100:
        return "Ставка должна быть от 1 до 100 псикоинов."
    return None


async def charge_stake(
    db: AsyncSession,
    *,
    user: User,
    stake: int,
    reason: str,
) -> tuple[bool, str]:
    error = validate_stake(stake)
    if error:
        return False, error
    if user.token_balance < stake:
        return False, (
            f"Для этой ставки нужно {psycoins(stake)}. Сейчас у вас {psycoins(user.token_balance)}."
        )

    user.token_balance -= stake
    user.status = calculate_status(user.subjectivity_score, user.token_balance)
    db.add(TokenLedgerEntry(user_id=user.id, amount=-stake, reason=reason))
    await db.flush()
    return True, "Ставка принята."


def set_solo_game(
    session: ConversationSession,
    *,
    action: str,
    prompt: str,
    stake: int,
    title: str | None = None,
    case_id: str | None = None,
    news_id: str | None = None,
) -> None:
    session.state = f"solo:{action}:1"
    write_session_payload(
        session,
        {
            "solo_game": {
                "action": action,
                "prompt": prompt,
                "stake": stake,
                "title": title,
                "case_id": case_id,
                "news_id": news_id,
            }
        },
    )


def get_solo_game(session: ConversationSession) -> dict | None:
    payload = read_session_payload(session).get("solo_game")
    return payload if isinstance(payload, dict) else None


def store_solo_agent_turn(
    session: ConversationSession,
    *,
    user_text: str,
    agent_reply: str,
) -> None:
    solo = get_solo_game(session) or {}
    solo["first_user_text"] = user_text
    solo["agent_reply"] = agent_reply
    write_session_payload(session, {"solo_game": solo})


def read_morning_question(session: ConversationSession) -> str | None:
    question = read_session_payload(session).get("morning_question")
    return str(question) if question else None


def onboarding_required_reply() -> str:
    return (
        "Сначала необходимо пройти испытание ETHOS.\n\n"
        "Отправьте /start, ответьте на 7 вопросов и дождитесь финального допуска."
    )


def system_entry_required_reply() -> str:
    return (
        "Проверка уже пройдена.\n\n"
        "Теперь откройте синюю кнопку возле поля отправки сообщений и нажмите "
        f"«Войти в систему». Вход в закрытый контур стоит {settings.system_entry_star_price} ⭐."
    )


def group_only_reply() -> str:
    return (
        "Баттлы проходят в закрытом групповом чате ETHOS.\n\n"
        "В личном чате можно пройти /case, посмотреть /profile или открыть /shop."
    )


async def has_custom_topic_privilege(db: AsyncSession, user: User) -> bool:
    if is_admin(user):
        return True
    return await user_owns_item_type(db, user, "privilege_custom_battle_topic")


def format_onboarding_case(case: Case, step: int) -> str:
    return (
        f"Испытание ETHOS {step}/{ONBOARDING_CASE_COUNT}\n\n"
        f"{case.prompt}\n\n"
        "Ответь коротко и честно: что ты сделаешь и почему именно так."
    )


def format_profile(user: User) -> str:
    status_labels = {
        "object": "Объект",
        "seeker": "Соискатель",
        "faithful": "Верный",
        "keeper": "Хранитель",
        "sighted": "Видящий",
        "subject": "Субъект",
    }
    summary = user.profile_summary or (
        "Профиль пока пустой. Пройдите /case, чтобы появилась первая оценка."
    )
    return (
        "Профиль ETHOS\n\n"
        f"Статус: {status_labels.get(user.status, user.status)}\n"
        f"Индекс субъектности: {user.subjectivity_score}/100\n"
        f"Баланс: {psycoins(user.token_balance)}\n\n"
        f"{summary}"
    )


def format_help() -> str:
    return (
        "Я — Оракул ИИ.\n\n"
        "В личном чате мы можем говорить о состоянии, сложном выборе и отношениях. "
        "В закрытой группе доступны баттлы, новости и кейсы.\n\n"
        "Команды:\n"
        "/case — короткий ETHOS-кейс с оценкой и псикоинами\n"
        "/case тема — свой кейс, если куплена привилегия\n"
        "/news — Sentinel Mode: реальная новость как этический кейс\n"
        "/news тема — свой новостной разбор, если куплена привилегия\n"
        "/battle — создать баттл на тему Оракула\n"
        "/battle тема — создать баттл на свою тему, если куплена привилегия\n"
        "/joinbattle — войти вторым участником\n"
        "/finishbattle — завершить баттл и выдать награду победителю\n"
        "/finishdiscussion — завершить групповой разбор кейса или новости\n"
        "/shop — магазин псикоинов\n"
        "/buy 1 — купить предмет, привилегию или Сферу Мудрости\n"
        "/profile — посмотреть профиль и баланс\n"
        "/help — показать это меню"
    )


def format_assessment_reply(title: str, assessment, token_delta: int) -> str:
    return (
        f"{title}\n\n"
        f"Субъектность: {assessment.subjectivity}/100\n"
        f"Честность: {assessment.honesty}/100\n"
        f"Эмоциональная устойчивость: {assessment.emotional_sovereignty}/100\n"
        f"Когнитивная гибкость: {assessment.cognitive_humility}/100\n"
        f"Эмпатия: {assessment.empathy}/100\n\n"
        f"{assessment.summary}\n\n"
        f"Начислено: {psycoins(token_delta)}"
    )


async def get_onboarding_assessments(
    db: AsyncSession, session: ConversationSession
) -> list[Assessment]:
    result = await db.execute(
        select(Assessment)
        .where(
            Assessment.session_id == session.id,
            Assessment.source == "onboarding_case",
        )
        .order_by(Assessment.created_at.asc())
    )
    return list(result.scalars().all())


async def get_next_onboarding_case(db: AsyncSession, session: ConversationSession) -> Case:
    assessments = await get_onboarding_assessments(db, session)
    used_case_ids = {
        assessment.case_id for assessment in assessments if assessment.case_id is not None
    }
    return await get_random_case(db, exclude_ids=used_case_ids)


async def build_onboarding_conclusion(
    db: AsyncSession,
    *,
    user: User,
    assessments: list[Assessment],
) -> str:
    assessment_text = "\n\n".join(
        (
            f"Ответ {index}: субъектность {assessment.subjectivity}/100, "
            f"честность {assessment.honesty}/100, "
            f"суверенитет {assessment.emotional_sovereignty}/100, "
            f"гибкость {assessment.cognitive_humility}/100, "
            f"эмпатия {assessment.empathy}/100.\n"
            f"Вывод: {assessment.summary}"
        )
        for index, assessment in enumerate(assessments, start=1)
    )
    fallback = (
        "<b>Испытание окончено.</b>\n\n"
        "<b>Анализ завершен.</b>\n\n"
        "В вас зафиксирован сильный потенциал субъекта.\n\n\n"
    
        "<b>ETHOS</b> — это не просто игра, а цифровой аудит твоей личности. "
        "Это пространство, где искусственный интеллект (Оракул) анализирует твои решения, "
        "слова и даже «послевкусие» твоих реальных встреч, чтобы определить твой истинный вес как человека.\n\n"
    
        "Здесь нет правильных ответов, есть только подлинные. "
        "Цель игры — пройти путь трансформации и доказать системе, "
        "что ты не просто «эхо» чужих мнений, а самостоятельная единица.\n\n\n"
    
        "<b>В чем разница между Объектом и Субъектом?</b>\n\n\n"
    
        "<b>ОБЪЕКТ</b>\n"
        "<i>Статус по умолчанию</i>\n\n"
    
        "Это человек-функция. Он действует реактивно: обижается, когда его задели, "
        "верит в то, что диктует лента новостей, и использует готовые шаблоны поведения. "
        "Объектом легко манипулировать, потому что его реакции предсказуемы. "
        "Он — материал для чужих решений.\n\n\n"
    
        "<b>СУБЪЕКТ</b>\n"
        "<i>Цель трансформации</i>\n\n"
    
        "Это человек-автор. Он обладает «внутренним стержнем» и осознанностью. "
        "Субъект сам выбирает свою реакцию даже в условиях давления. "
        "Он видит манипуляции, берет ответственность за свои ошибки "
        "и сохраняет верность своим ценностям (своему «Эху»), даже когда это невыгодно. "
        "Он — источник смыслов.\n\n\n"
    
        "Твой путь в ETHOS — это процесс отделения себя от навязанных программ. "
        "Оракул будет зеркалить тебя до тех пор, пока ты либо не сдашься, "
        "либо не обретешь субъектность.\n\n\n"
    
        "Ваш следующий шаг — войти в систему ETHOS.\n"
        "Станьте частью сообщества, где проходят психологические баттлы, "
        "разборы кейсов и испытания на субъектность."
    )
    try:
        conclusion = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты Оракул ETHOS. На основе семи первичных оценок дай пользователю "
                        "краткий, прямой и эстетичный вывод. Без диагнозов. Нужно: 1) что "
                        "видно по человеку, 2) зона роста. "
                        "Затем добавь пояснение что такое ETHOS, Субъект и Объект (используй текст пользователя). "
                        "В конце обязательно: 'Ваш следующий шаг — войти в систему ETHOS. Станьте частью сообщества...' и призыв открыть приложение. "
                        "Без повторов. Обращение на 'вы'."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Пользователь: @{user.username or 'без username'}\n"
                        f"Текущий индекс субъектности: {user.subjectivity_score}/100\n\n"
                        f"{assessment_text}"
                    ),
                },
            ],
            temperature=0.35,
            max_tokens=800,
        )
    except Exception:
        return fallback

    return clean_generated_text(conclusion, split_sections=True)


async def start_pending_game(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession,
    chat_id: int | None,
    chat_type: str | None,
) -> tuple[str, str, int, InlineKeyboardMarkup | None]:
    pending = get_pending_game(session)
    if pending is None:
        session.state = "active"
        clear_session_payload(session)
        return "Сценарий не найден. Запустите /battle, /case или /news заново.", "game_missing", 0, None

    action = str(pending.get("action") or "")
    mode = str(pending.get("mode") or "")
    topic = str(pending.get("topic") or "").strip() or None
    stake = int(pending.get("stake") or 0)
    if action not in GAME_ACTION_LABELS:
        session.state = "active"
        clear_session_payload(session)
        return "Не понял сценарий. Запустите /battle, /case или /news заново.", "game_bad", 0, None
    if mode not in GAME_MODE_LABELS:
        session.state = "game:mode"
        return format_mode_prompt(action), "game_mode_prompt", 0, game_mode_reply_markup()
    stake_error = validate_stake(stake)
    if stake_error:
        session.state = "game:stake"
        return stake_error, "game_stake_bad", 0, stake_reply_markup()
    if user.token_balance < stake:
        return (
            f"Для этой ставки нужно {psycoins(stake)}. Сейчас у вас {psycoins(user.token_balance)}.",
            "game_stake_rejected",
            0,
            stake_reply_markup(),
        )

    if mode == "human" and not is_group_chat(chat_type):
        session.state = "game:mode"
        return (
            "С человеком можно играть только в закрытом групповом чате.\n\n"
            "Здесь можно выбрать соло с ИИ-агентом.",
            "game_human_group_only",
            0,
            game_mode_reply_markup(),
        )

    if action == "battle":
        if mode == "human":
            battle = await create_battle(db, user=user, chat_id=chat_id, topic=topic)
            ok, message = await choose_battle_entry_fee(
                db,
                battle=battle,
                user=user,
                entry_fee=stake,
            )
            if ok:
                session.state = "active"
                clear_session_payload(session)
            return (
                message,
                "battle_waiting" if ok else "battle_fee_rejected",
                0,
                battle_join_reply_markup(battle.id) if ok else stake_reply_markup(),
            )

        prompt = topic or await generate_battle_topic()
        ok, message = await charge_stake(
            db,
            user=user,
            stake=stake,
            reason=f"PsyCoin solo battle stake: {user.id}",
        )
        if not ok:
            return message, "game_stake_rejected", 0, stake_reply_markup()
        set_solo_game(session, action="battle", prompt=prompt, stake=stake, title="Баттл")
        return (
            "Баттл с ИИ-агентом начат.\n\n"
            f"Тема: {prompt}\n\n"
            f"Ставка списана: {psycoins(stake)}.\n"
            "Первый ход за вами. Напишите позицию так, как сказали бы живому оппоненту.",
            "solo_battle_started",
            0,
            None,
        )

    if action == "case":
        case = await create_custom_case(db, topic) if topic else await get_random_case(db)
        if mode == "human":
            discussion = await create_case_discussion(db, user=user, chat_id=chat_id, case=case)
            ok, message = await join_discussion(
                db,
                discussion=discussion,
                user=user,
                entry_fee=stake,
            )
            if not ok:
                return message, "discussion_join_rejected", 0, stake_reply_markup()
            session.state = "active"
            clear_session_payload(session)
            return (
                f"{message}\n\n{format_discussion_prompt(discussion)}",
                "case_discussion_opened",
                0,
                discussion_join_reply_markup(discussion.id),
            )

        ok, message = await charge_stake(
            db,
            user=user,
            stake=stake,
            reason=f"PsyCoin solo case stake: {case.id}",
        )
        if not ok:
            return message, "game_stake_rejected", 0, stake_reply_markup()
        set_solo_game(
            session,
            action="case",
            prompt=case.prompt,
            stake=stake,
            title=case.title,
            case_id=str(case.id),
        )
        return (
            f"Разбор кейса с ИИ-агентом начат. Ставка списана: {psycoins(stake)}.\n\n"
            f"{format_case(case)}",
            "solo_case_started",
            0,
            None,
        )

    if action == "news":
        item = await create_custom_news_case(db, topic) if topic else await get_or_create_news_case(db)
        if mode == "human":
            discussion = await create_news_discussion(db, user=user, chat_id=chat_id, item=item)
            ok, message = await join_discussion(
                db,
                discussion=discussion,
                user=user,
                entry_fee=stake,
            )
            if not ok:
                return message, "discussion_join_rejected", 0, stake_reply_markup()
            session.state = "active"
            clear_session_payload(session)
            return (
                f"{message}\n\n{format_discussion_prompt(discussion)}",
                "news_discussion_opened",
                0,
                discussion_join_reply_markup(discussion.id),
            )

        ok, message = await charge_stake(
            db,
            user=user,
            stake=stake,
            reason=f"PsyCoin solo news stake: {item.id}",
        )
        if not ok:
            return message, "game_stake_rejected", 0, stake_reply_markup()
        set_solo_game(
            session,
            action="news",
            prompt=item.ethical_case,
            stake=stake,
            title=item.title,
            news_id=str(item.id),
        )
        return (
            "Sentinel Mode с ИИ-агентом начат.\n\n"
            f"Ставка списана: {psycoins(stake)}.\n\n"
            f"{item.ethical_case}\n\n"
            "Займите позицию: где здесь факт, где реакция, и какой выбор сохранит достоинство?",
            "solo_news_started",
            0,
            None,
        )

    session.state = "active"
    clear_session_payload(session)
    return "Не понял сценарий. Запустите /battle, /case или /news заново.", "game_bad", 0, None


async def handle_solo_game_turn(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession,
    text: str,
) -> tuple[str, str, int, InlineKeyboardMarkup | None]:
    solo = get_solo_game(session)
    if solo is None:
        session.state = "active"
        clear_session_payload(session)
        return "Соло-сценарий не найден. Запустите /battle, /case или /news заново.", "solo_missing", 0, None

    parts = session.state.split(":")
    action = str(solo.get("action") or "case")
    step = parts[2] if len(parts) > 2 else "1"
    prompt = str(solo.get("prompt") or "")
    stake = int(solo.get("stake") or 0)

    if step == "1":
        implicit = analyze_implicit_signals(text)
        agent_reply = await generate_ai_agent_reply(
            activity_type=action,
            prompt=prompt,
            user_text=text,
        )
        store_solo_agent_turn(session, user_text=text, agent_reply=agent_reply)
        session.state = f"solo:{action}:2"
        return (
            f"{agent_reply}\n\nВопрос от Оракула: {build_probe_question(text, implicit)}\n\n"
            "Ваш финальный ход?",
            f"solo_{action}_agent_reply",
            0,
            None,
        )

    first_user_text = str(solo.get("first_user_text") or "").strip()
    agent_reply = str(solo.get("agent_reply") or "").strip()
    combined_answer = "\n\n".join(part for part in [first_user_text, text] if part)
    implicit = analyze_implicit_signals(combined_answer)
    raw_case_id = solo.get("case_id")
    case_id = None
    if raw_case_id:
        try:
            case_id = UUID(str(raw_case_id))
        except ValueError:
            case_id = None
    assessment, assessment_delta = await create_assessment(
        db,
        user=user,
        text=combined_answer,
        source=f"solo_{action}",
        case_id=case_id,
        session_id=session.id,
        case_prompt=prompt,
        implicit_signals=implicit,
    )
    avg_score = assessment_average_score(assessment)
    won = avg_score >= SOLO_RESULT_WIN_THRESHOLD
    payout = stake * 2 if won else 0
    if payout:
        user.token_balance += payout
        user.status = calculate_status(user.subjectivity_score, user.token_balance)
        db.add(
            TokenLedgerEntry(
                user_id=user.id,
                amount=payout,
                reason=f"PsyCoin solo {action} win payout",
                assessment_id=assessment.id,
            )
        )
        await db.flush()

    session.state = "active"
    clear_session_payload(session)
    title = {
        "battle": "Итог баттла с ИИ-агентом",
        "case": "Итог разбора с ИИ-агентом",
        "news": "Итог Sentinel Mode с ИИ-агентом",
    }.get(action, "Итог с ИИ-агентом")
    result_line = (
        f"Ставка сыграла: +{psycoins(payout)}."
        if won
        else "Ставка не сыграла. Оракул оставил ее в системе как плату за разбор."
    )
    reply = (
        f"{title}\n\n"
        f"Ответ ИИ-агента:\n{agent_reply or 'Оппонентская позиция была учтена.'}\n\n"
        f"{result_line}\n\n"
        + format_assessment_reply("Оценка ответа", assessment, assessment_delta)
        + f"\n\nИтого по сценарию: {psycoins(assessment_delta + payout)}."
    )
    return reply, f"solo_{action}_finished", assessment_delta + payout, None


async def handle_user_text(
    db: AsyncSession,
    *,
    user: User,
    session: ConversationSession,
    text: str,
    chat_id: int | None = None,
    chat_type: str | None = None,
) -> tuple[str, str, int, InlineKeyboardMarkup | None]:
    clean = text.strip()
    token = clean.split(maxsplit=1)[0] if clean else ""
    command = normalize_command_token(token)
    admin_user = is_admin(user)

    if admin_user:
        if session.state != "active":
            session.state = "active"
        if command == "/start":
            return format_admin_help(success_prefix=False), "admin_start", 0, None

        # ==================== АДМИН-КОМАНДЫ ====================
        # Эти команды здесь оставлены для обратной совместимости, но основной обработчик в admin_tools.py
        # Перенаправляем на admin_tools
        if command in {"/grant", "/addcoins", "/setscore", "/setstatus", "/setlifecycle", "/reset", "/close", "/shoplink", "/users", "/user", "/withdrawals", "/withdrawdone"}:
            from app.services.admin_tools import handle_admin_tool_command
            result = await handle_admin_tool_command(db, user, clean)
            if result:
                await db.commit()
                return result, "admin_command", 0, None

        if command == "/case" and chat_type not in {"group", "supergroup"}:
            parts = clean.split(maxsplit=1)
            case = (
                await create_custom_case(db, parts[1].strip())
                if len(parts) > 1 and parts[1].strip()
                else await get_random_case(db)
            )
            return (
                format_admin_success("Админ-превью кейса\n\n" + format_case(case)),
                "admin_case_preview",
                0,
                None,
            )
        if command == "/news" and chat_type not in {"group", "supergroup"}:
            parts = clean.split(maxsplit=1)
            item = (
                await create_custom_news_case(db, parts[1].strip())
                if len(parts) > 1 and parts[1].strip()
                else await get_or_create_news_case(db)
            )
            return (
                format_admin_success(
                    "Админ-превью новости\n\n"
                    f"{item.ethical_case}\n\n"
                    f"Источник: {item.url or item.source}"
                ),
                "admin_news_preview",
                0,
                None,
            )

    if session.state.startswith("onboarding:case:") and command.startswith("/") and command != "/help":
        return (
            "Вы сейчас проходите входную проверку ETHOS. Завершите текущий кейс и только потом используйте другие команды.",
            "onboarding_in_progress",
            0,
            None,
        )

    if (
        user.lifecycle_status == "newbie"
        and not admin_user
        and command not in {"/start", "/help"}
        and not is_onboarding_state(session.state)
    ):
        return onboarding_required_reply(), "onboarding_required", 0, first_contact_reply_markup()

    if (
        user.lifecycle_status == "beginner"
        and not admin_user
        and is_gameplay_request(command, clean)
    ):
        return system_entry_required_reply(), "system_entry_required", 0, None

    if command == "/cancel" or clean in {"playcancel", "confirm:no"}:
        session.state = "active"
        clear_session_payload(session)
        return "Отменено. Можно начать заново: /battle, /case или /news.", "game_cancelled", 0, None

    if clean.startswith("playmode:"):
        mode = clean.split(":", maxsplit=1)[1]
        if mode not in {"ai", "human"}:
            return "Не понял формат. Выберите один из вариантов.", "game_mode_bad", 0, game_mode_reply_markup()
        pending = get_pending_game(session)
        if pending is None:
            session.state = "active"
            return (
                "Сценарий не найден. Запустите /battle, /case или /news заново.",
                "game_missing",
                0,
                None,
            )
        if mode == "human" and not is_group_chat(chat_type):
            session.state = "game:mode"
            return (
                "С человеком можно играть только в закрытом групповом чате.\n\n"
                "Для личного чата выберите соло с ИИ-агентом.",
                "game_human_group_only",
                0,
                game_mode_reply_markup(),
            )
        pending = update_pending_game(session, mode=mode) or pending
        session.state = "game:stake"
        return format_stake_prompt(pending), "game_stake_prompt", 0, stake_reply_markup()

    if clean == "stake_other":
        if get_pending_game(session) is None:
            return "Сначала выберите сценарий: /battle, /case или /news.", "game_missing", 0, None
        session.state = "game:stake"
        return (
            "Отправьте ставку вручную: /stake 7. Допустимый диапазон: 1-100 псикоинов.",
            "game_stake_help",
            0,
            None,
        )

    if clean.startswith("stake:") or command == "/stake":
        if clean.startswith("stake:"):
            raw_stake = clean.split(":", maxsplit=1)[1]
        else:
            parts = clean.split(maxsplit=1)
            raw_stake = parts[1].strip() if len(parts) > 1 else ""
        stake = parse_positive_int(raw_stake)
        if stake is None:
            return "Ставка должна быть числом: /stake 7", "game_stake_bad", 0, stake_reply_markup()
        error = validate_stake(stake)
        if error:
            return error, "game_stake_bad", 0, stake_reply_markup()
        pending = update_pending_game(session, stake=stake)
        if pending is None:
            session.state = "active"
            return (
                "Сценарий не найден. Запустите /battle, /case или /news заново.",
                "game_missing",
                0,
                None,
            )
        session.state = "game:confirm"
        return (
            format_confirmation_prompt(pending),
            "game_confirmation",
            0,
            game_confirmation_reply_markup(),
        )

    if clean == "confirm:yes":
        return await start_pending_game(
            db,
            user=user,
            session=session,
            chat_id=chat_id,
            chat_type=chat_type,
        )

    if clean.startswith("bfee_other:"):
        return (
            "Отправьте уровень вручную: /battlefee 7. Допустимый диапазон: 1-100 псикоинов.",
            "battle_fee_help",
            0,
            None,
        )

    if clean.startswith("bfee:"):
        parts = clean.split(":")
        if len(parts) != 3:
            return "Не понял уровень баттла. Запустите /battle еще раз.", "battle_fee_bad", 0, None
        try:
            battle_id = UUID(parts[1])
            entry_fee = int(parts[2])
        except ValueError:
            return "Не понял уровень баттла. Запустите /battle еще раз.", "battle_fee_bad", 0, None
        battle = await get_battle_by_id(db, battle_id)
        if battle is None:
            return "Баттл не найден. Запустите новый: /battle", "battle_missing", 0, None
        ok, message = await choose_battle_entry_fee(
            db,
            battle=battle,
            user=user,
            entry_fee=entry_fee,
        )
        return (
            message,
            "battle_waiting" if ok else "battle_fee_rejected",
            0,
            battle_join_reply_markup(battle.id) if ok else None,
        )

    if clean.startswith("bjoin:"):
        parts = clean.split(":")
        try:
            battle_id = UUID(parts[1])
        except (IndexError, ValueError):
            return "Баттл не найден. Запустите новый: /battle", "battle_missing", 0, None
        battle, message = await join_waiting_battle(db, user=user, chat_id=chat_id, battle_id=battle_id)
        return (
            message,
            "battle_join",
            0,
            battle_finish_reply_markup(battle.id) if battle is not None and battle.status == "active" else None,
        )

    if clean.startswith("bfinish:"):
        parts = clean.split(":")
        try:
            battle_id = UUID(parts[1])
        except (IndexError, ValueError):
            return "Баттл не найден.", "battle_missing", 0, None
        _, message, token_delta = await finish_active_battle(
            db,
            chat_id=chat_id,
            battle_id=battle_id,
        )
        return message, "battle_finished", token_delta, None

    if clean.startswith("djoin:"):
        parts = clean.split(":")
        if len(parts) != 3:
            return "Не понял уровень участия.", "discussion_join_bad", 0, None
        try:
            discussion_id = UUID(parts[1])
            entry_fee = int(parts[2])
        except ValueError:
            return "Не понял уровень участия.", "discussion_join_bad", 0, None
        discussion = await get_discussion_by_id(db, discussion_id)
        if discussion is None:
            return "Обсуждение не найдено.", "discussion_missing", 0, None
        ok, message = await join_discussion(
            db,
            discussion=discussion,
            user=user,
            entry_fee=entry_fee,
        )
        return (
            message,
            "discussion_join" if ok else "discussion_join_rejected",
            0,
            discussion_join_reply_markup(discussion.id) if ok else None,
        )

    if clean.startswith("dfinish:"):
        parts = clean.split(":")
        try:
            discussion_id = UUID(parts[1])
        except (IndexError, ValueError):
            return "Обсуждение не найдено.", "discussion_missing", 0, None
        _, message, token_delta = await finish_discussion(
            db,
            chat_id=chat_id,
            discussion_id=discussion_id,
        )
        return message, "discussion_finished", token_delta, None

    if command == "/start":
        if user.lifecycle_status == "beginner" and not admin_user:
            return (
                "Проверка уже пройдена.\n\n"
                "Нажмите синюю кнопку возле поля отправки сообщений, откройте ETHOS "
                f"и войдите в систему за {settings.system_entry_star_price} ⭐.",
                "onboarding_already_completed",
                0,
                None,
            )
        if user.lifecycle_status == "follower" and not admin_user:
            return (
                "Вы уже в системе ETHOS.\n\n"
                "Откройте синюю кнопку возле поля отправки сообщений, чтобы перейти в магазин, "
                "профиль и баланс.",
                "system_ready",
                0,
                None,
            )
        session.state = "onboarding:consent"
        user.status = user.status or "object"
        return format_first_contact(), "onboarding_start", 0, first_contact_reply_markup()

    if session.state == "onboarding:consent":
        lower = clean.lower()
        if clean == "onboarding:ready" or any(
            marker in lower for marker in ["готов", "зеркало", "начать", "да"]
        ):
            case = await get_next_onboarding_case(db, session)
            session.state = f"onboarding:case:{case.id}:1"
            return format_onboarding_case(case, 1), "onboarding_case_prompt", 0, None
        if clean == "onboarding:later" or any(
            marker in lower for marker in ["время", "позже", "выход", "нет"]
        ):
            session.state = "paused"
            return (
                "Пауза зафиксирована. Когда будешь готов продолжить, отправь /start.",
                "onboarding_paused",
                0,
                None,
            )
        return (
            "Сейчас нет меню и обходных дверей. Выбери один из двух вариантов ниже.",
            "onboarding_waiting",
            0,
            first_contact_reply_markup(),
        )

    if session.state.startswith("onboarding:case:"):
        parts = session.state.split(":")
        case_id = parts[2] if len(parts) > 2 else ""
        step = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        result = await db.execute(select(Case).where(Case.id == UUID(case_id)))
        case = result.scalar_one_or_none()
        if case is None:
            case = await get_next_onboarding_case(db, session)
            session.state = f"onboarding:case:{case.id}:{step}"
            return format_onboarding_case(case, step), "onboarding_case_prompt", 0, None

        latency = await get_last_assistant_latency_seconds(db, session)
        implicit = analyze_implicit_signals(clean, latency_seconds=latency)
        _, token_delta = await create_assessment(
            db,
            user=user,
            text=clean,
            source="onboarding_case",
            case_id=case.id,
            session_id=session.id,
            case_prompt=case.prompt,
            implicit_signals=implicit,
        )
        assessments = await get_onboarding_assessments(db, session)
        if len(assessments) >= ONBOARDING_CASE_COUNT:
            session.state = "active"
            user.subjectivity_score = calculate_onboarding_initial_score(assessments)
            user.status = calculate_status(user.subjectivity_score, user.token_balance)
            conclusion = await build_onboarding_conclusion(db, user=user, assessments=assessments)
            user.lifecycle_status = "beginner"
            user.profile_summary = extract_profile_summary(conclusion)
            user.token_balance += 10
            return conclusion, "onboarding_completed", token_delta + 10, None

        next_step = len(assessments) + 1
        next_case = await get_next_onboarding_case(db, session)
        session.state = f"onboarding:case:{next_case.id}:{next_step}"
        reply = (
            "Ответ принят. Я зафиксировал не только слова, но и способ выбора.\n\n"
            "Следующее испытание.\n\n"
            + format_onboarding_case(next_case, next_step)
        )
        return reply, "onboarding_case_prompt", token_delta, None

    if session.state == "morning:wait" and not command.startswith("/"):
        if morning_question_replacement_requested(clean):
            question = await generate_morning_challenge_question()
            write_session_payload(session, {"morning_question": question})
            return (
                "Конечно, заменяю вопрос.\n\n"
                f"{question}\n\n"
                "Ответьте одним сообщением, как поступили бы в этой ситуации.",
                "morning_question_replaced",
                0,
                None,
            )
        question = read_morning_question(session)
        session.state = "active"
        clear_session_payload(session)
        return await process_morning_case_response(db, user, clean, question=question)

    if session.state.startswith("solo:"):
        if command.startswith("/") and command != "/help":
            return (
                "Сейчас идет соло-сценарий с ИИ-агентом. Ответьте на текущий ход "
                "или отмените сценарий командой /cancel.",
                "solo_in_progress",
                0,
                None,
            )
        if not command.startswith("/"):
            return await handle_solo_game_turn(db, user=user, session=session, text=clean)

    if (
        session.state.startswith("game:")
        and command != "/help"
        and not clean.startswith(GAMEPLAY_CALLBACK_PREFIXES)
    ):
        if session.state == "game:mode":
            pending = get_pending_game(session)
            if pending is not None:
                return (
                    format_mode_prompt(str(pending.get("action") or "")),
                    "game_mode_prompt",
                    0,
                    game_mode_reply_markup(),
                )
        if session.state == "game:stake":
            stake = parse_positive_int(clean)
            if stake is not None:
                error = validate_stake(stake)
                if error:
                    return error, "game_stake_bad", 0, stake_reply_markup()
                pending = update_pending_game(session, stake=stake)
                if pending is not None:
                    session.state = "game:confirm"
                    return (
                        format_confirmation_prompt(pending),
                        "game_confirmation",
                        0,
                        game_confirmation_reply_markup(),
                    )
            pending = get_pending_game(session)
            if pending is not None:
                return format_stake_prompt(pending), "game_stake_prompt", 0, stake_reply_markup()
        if session.state == "game:confirm":
            pending = get_pending_game(session)
            if pending is not None:
                return (
                    format_confirmation_prompt(pending),
                    "game_confirmation",
                    0,
                    game_confirmation_reply_markup(),
                )

    if command == "/help":
        return format_help(), "help", 0, None
    if command in {"/profile", "/status"}:
        return format_profile(user), "profile", 0, None
    if command == "/reset":
        return "Эта команда доступна только администратору.", "forbidden", 0, None
    if command == "/case":
        parts = clean.split(maxsplit=1)
        topic = parts[1].strip() if len(parts) > 1 else None
        if topic and not await has_custom_topic_privilege(db, user):
            return (
                "Своя тема кейса доступна после покупки привилегии в магазине. "
                "Запустите /case без темы или активируйте подписку в /shop.",
                "case_topic_locked",
                0,
                None,
            )
        set_pending_game(session, action="case", topic=topic, chat_type=chat_type)
        return format_mode_prompt("case"), "game_mode_prompt", 0, game_mode_reply_markup()
    if command == "/news":
        parts = clean.split(maxsplit=1)
        topic = parts[1].strip() if len(parts) > 1 else None
        if topic and not await has_custom_topic_privilege(db, user):
            return (
                "Своя тема новости доступна после покупки привилегии в магазине. "
                "Запустите /news без темы или активируйте подписку в /shop.",
                "news_topic_locked",
                0,
                None,
            )
        set_pending_game(session, action="news", topic=topic, chat_type=chat_type)
        return format_mode_prompt("news"), "game_mode_prompt", 0, game_mode_reply_markup()
    if command == "/battle":
        parts = clean.split(maxsplit=1)
        topic = parts[1].strip() if len(parts) > 1 else None
        if topic and not await has_custom_topic_privilege(db, user):
            return (
                "Своя тема баттла — платная привилегия. Купите ее в /shop "
                "или запустите /battle без темы: тогда тему предложит Оракул.",
                "battle_topic_locked",
                0,
                None,
            )
        set_pending_game(session, action="battle", topic=topic, chat_type=chat_type)
        return format_mode_prompt("battle"), "game_mode_prompt", 0, game_mode_reply_markup()
    if command == "/battlefee":
        if not is_group_chat(chat_type):
            return group_only_reply(), "battle_group_only", 0, None
        parts = clean.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            return "Выберите уровень: /battlefee 1-100", "battle_fee_help", 0, None
        battle = await get_latest_battle(
            db,
            chat_id=chat_id,
            statuses=["configuring"],
            created_by_user_id=user.id,
        )
        if battle is None:
            return "У вас нет баттла, ожидающего выбора уровня. Запустите /battle.", "battle_missing", 0, None
        ok, message = await choose_battle_entry_fee(
            db,
            battle=battle,
            user=user,
            entry_fee=int(parts[1].strip()),
        )
        return (
            message,
            "battle_waiting" if ok else "battle_fee_rejected",
            0,
            battle_join_reply_markup(battle.id) if ok else None,
        )
    if command == "/joinbattle":
        if not is_group_chat(chat_type):
            return group_only_reply(), "battle_group_only", 0, None
        battle, message = await join_waiting_battle(db, user=user, chat_id=chat_id)
        return (
            message,
            "battle_join",
            0,
            battle_finish_reply_markup(battle.id) if battle is not None and battle.status == "active" else None,
        )
    if command == "/finishbattle":
        if not is_group_chat(chat_type):
            return group_only_reply(), "battle_group_only", 0, None
        _, message, token_delta = await finish_active_battle(db, chat_id=chat_id)
        return message, "battle_finished", token_delta, None
    if command in {"/finishdiscussion", "/finishcase", "/finishnews"}:
        _, message, token_delta = await finish_discussion(db, chat_id=chat_id)
        return message, "discussion_finished", token_delta, None
    if command == "/shop":
        if user.lifecycle_status == "admin":
            return (
                "Админ-панель ETHOS (команды в боте):\n\n"
                "/grant <id> <кол-во> — выдать псикоины\n"
                "/setscore <id> <0-100> — установить индекс\n"
                "/setstatus <id> <статус> — изменить статус\n"
                "/setlifecycle <id> <этап> — изменить этап\n"
                "/resetuser <id> — полный сброс\n"
                "/users — список пользователей\n\n"
                "Все команды работают прямо в этом чате.",
                "admin_panel",
                0,
                None,
            )
        if user.lifecycle_status == "newbie" and not is_admin(user):
            return (
                "Ты здесь слишком рано. Ты еще не готов. Оракул ожидает тебя в чате.",
                "shop_locked",
                0,
                None,
            )
        if user.lifecycle_status == "beginner" and not is_admin(user):
            return (
                "Проверка пройдена. Теперь открой синюю кнопку возле поля отправки сообщений "
                f"и нажми «Войти в систему». Вход в закрытый контур стоит {settings.system_entry_star_price} ⭐.",
                "shop_entry_required",
                0,
                None,
            )
        return (
            await format_shop(db, user)
            + "\n\nВеб-витрина для теста: "
            + settings.public_webapp_url
            + f"?telegram_id={user.telegram_id}",
            "shop",
            0,
                None,
            )
    if command == "/buy":
        if user.lifecycle_status != "follower" and not is_admin(user):
            return (
                "Покупки откроются после входа в систему ETHOS через синюю кнопку mini-app.",
                "buy_locked",
                0,
                None,
            )
        parts = clean.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            return "Напишите номер предмета, например: /buy 1", "buy_help", 0, None
        return await buy_item(db, user, int(parts[1].strip())), "buy", 0, None

    if session.state.startswith("case:"):
        parts = session.state.split(":")
        case_id = parts[1]
        step = parts[2] if len(parts) > 2 else "2"
        result = await db.execute(select(Case).where(Case.id == UUID(case_id)))
        case = result.scalar_one_or_none()
        if case is None:
            session.state = "active"
            return (
                "Кейс не найден, поэтому я вернул вас в обычный режим. Можно начать новый: /case",
                "case_missing",
                0,
                None,
            )
        latency = await get_last_assistant_latency_seconds(db, session)
        implicit = analyze_implicit_signals(clean, latency_seconds=latency)
        if step == "1":
            session.state = f"case:{case.id}:2"
            return (
                "Ответ зафиксирован. Теперь проверим мотив.\n\n"
                + build_probe_question(clean, implicit),
                "case_probe",
                0,
                None,
            )
        session.state = "active"
        answers = await get_recent_user_texts(db, session, limit=2)
        combined_answer = "\n\n".join(answers) or clean
        combined_implicit = analyze_implicit_signals(combined_answer, latency_seconds=latency)
        assessment, token_delta = await create_assessment(
            db,
            user=user,
            text=combined_answer,
            source="case_answer",
            case_id=case.id,
            session_id=session.id,
            case_prompt=case.prompt,
            implicit_signals=combined_implicit,
        )
        reply = format_assessment_reply("Разбор ETHOS", assessment, token_delta)
        reply += (
            "\n\nЧтобы пройти еще один кейс, отправьте /case. "
            "Для разговора просто напишите сообщение."
        )
        return reply, "case_assessment", token_delta, None


    if session.state.startswith("news:"):
        parts = session.state.split(":")
        news_id = parts[1]
        step = parts[2] if len(parts) > 2 else "2"
        result = await db.execute(select(NewsItem).where(NewsItem.id == UUID(news_id)))
        item = result.scalar_one_or_none()
        if item is None:
            session.state = "active"
            return "Новостной кейс не найден. Можно начать новый: /news", "news_missing", 0, None
        latency = await get_last_assistant_latency_seconds(db, session)
        implicit = analyze_implicit_signals(clean, latency_seconds=latency)
        if step == "1":
            session.state = f"news:{item.id}:2"
            return (
                "Позиция принята. Теперь отдели факт от своей реакции.\n\n"
                + build_probe_question(clean, implicit),
                "news_probe",
                0,
                None,
            )
        session.state = "active"
        answers = await get_recent_user_texts(db, session, limit=2)
        combined_answer = "\n\n".join(answers) or clean
        combined_implicit = analyze_implicit_signals(combined_answer, latency_seconds=latency)
        assessment, token_delta = await create_assessment(
            db,
            user=user,
            text=combined_answer,
            source="news_sentinel",
            session_id=session.id,
            case_prompt=item.ethical_case,
            implicit_signals=combined_implicit,
        )
        reply = format_assessment_reply("Разбор Sentinel Mode", assessment, token_delta)
        return reply, "news_assessment", token_delta, None

    if is_group_chat(chat_type):
        active_battle = await get_latest_battle(db, chat_id=chat_id, statuses=["active"])
        if active_battle is not None:
            return "Аргумент зафиксирован для текущего баттла.", "battle_argument", 0, None
        active_discussion = await get_latest_discussion(
            db,
            chat_id=chat_id,
            statuses=["active"],
        )
        if active_discussion is not None:
            return "Вклад зафиксирован для текущего обсуждения.", "discussion_argument", 0, None
        return (
            "В группе я реагирую на команды: /battle, /joinbattle, /finishbattle, "
            "/news, /case, /finishdiscussion.",
            "group_idle",
                0,
                None,
            )

    reply = await build_supportive_reply_with_context(db, session=session, text=clean)
    if not admin_user:
        await create_assessment(
            db,
            user=user,
            text=clean,
            source="support_signal",
            session_id=session.id,
            implicit_signals=analyze_implicit_signals(clean),
            use_llm=False,
            award_tokens=False,
        )
    return reply, "support", 0, None
