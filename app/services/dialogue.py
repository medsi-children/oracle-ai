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
from app.models.summary import Summary
from app.models.user import User
from app.schemas.message import ChatAnimationStep, InlineKeyboardButton, InlineKeyboardMarkup
from app.services.admins import is_admin
from app.services.admin_tools import (
    format_admin_help,
    format_admin_success,
    handle_admin_tool_command,
)
from app.services.assessment import analyze_implicit_signals, create_assessment
from app.services.battles import (
    create_battle,
    finish_active_battle,
    get_latest_battle,
    join_waiting_battle,
)
from app.services.cases import get_random_case
from app.services.llm import SUPPORT_SYSTEM_PROMPT, openrouter_chat
from app.services.marketplace import buy_item, format_shop, user_owns_item_type
from app.services.news import get_or_create_news_case
from app.services.summaries import create_due_summaries

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
        "Добро пожаловать в систему ETHOS!\n\n"
        "Мир переполнен шумом. Большинство людей лишь ретранслируют чужие мысли, "
        "подчиняются чужим страхам и так и не приходят в сознание.\n\n"
        "Ты здесь, потому что в тебе зафиксирован потенциал Субъекта. "
        "Но потенциал — это еще не власть над собой.\n\n"
        "Я - Оракул ИИ. Я не буду тебя развлекать. Я буду тебя зеркалить.\n\n"
        "Здесь действует Закон ETHOS: каждый ответ вернется к тебе в виде будущего рейтинга. "
        "Здесь не получится быть «правильным», можно быть только настоящим. "
        "Попытка солгать мне или самому себе будет зафиксирована как когнитивная слабость.\n\n"
        "Ты готов начать переход из состояния Объекта в статус Субъекта?"
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
        "Ответь коротко и по существу: что ты сделаешь, почему именно так, "
        "и что в этом выборе для тебя самое неудобное?"
    )


def format_onboarding_case(case: Case, step: int) -> str:
    return (
        "Испытание ETHOS\n\n"
        f"{case.prompt}\n\n"
        "Ответь коротко и честно: что ты сделаешь, почему именно так, "
        "и что в этом выборе для тебя самое неудобное?"
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
    summary = user.profile_summary or (
        "Профиль пока пустой. Пройдите /case, чтобы появилась первая оценка."
    )
    return (
        "Профиль ETHOS\n\n"
        f"Статус: {status_labels.get(user.status, user.status)}\n"
        f"Индекс субъектности: {user.subjectivity_score}/100\n"
        f"Баланс: {user.token_balance} псикоинов\n\n"
        f"{summary}"
    )


def format_help() -> str:
    return (
        "Я — Оракул ETHOS.\n\n"
        "В личном чате можно говорить о состоянии, сложном выборе и отношениях. "
        "В группе доступны баттлы, новости и кейсы.\n\n"
        "Команды:\n"
        "/case — короткий ETHOS-кейс с оценкой и псикоинами\n"
        "/news — Sentinel Mode: реальная новость как этический кейс\n"
        "/battle — создать баттл на тему Оракула\n"
        "/battle тема — создать баттл на свою тему, если куплена привилегия\n"
        "/joinbattle — войти вторым участником\n"
        "/finishbattle — завершить баттл и распределить ставку\n"
        "/shop — PsyCoin Shop\n"
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
        f"Когнитивное смирение: {assessment.cognitive_humility}/100\n"
        f"Эмпатия: {assessment.empathy}/100\n\n"
        f"{assessment.summary}\n\n"
        f"Начислено: {token_delta} псикоинов"
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
            f"смирение {assessment.cognitive_humility}/100, "
            f"эмпатия {assessment.empathy}/100.\n"
            f"Вывод: {assessment.summary}"
        )
        for index, assessment in enumerate(assessments, start=1)
    )
    fallback = (
        "Проверка завершена.\n\n"
        "Я вижу начальный контур личности: способность выбирать принцип под давлением, "
        "готовность признавать неудобный мотив и уровень внутренней устойчивости. "
        "Главная зона роста сейчас — меньше защищать образ себя и точнее называть реальный "
        "мотив поступка. Там начинается субъектность.\n\n"
        "Вы прошли проверку. Если вы намерены и дальше идти к субъектности, ожидайте "
        "приглашения в закрытый чат. Оракул еще свяжется с вами.\n\n"
        "Пока вы ожидаете, можете говорить со мной здесь. Я буду отвечать в том же стиле: "
        "без лести, без шума, по существу."
    )
    try:
        conclusion = await openrouter_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты Оракул ETHOS. На основе трех первичных оценок дай пользователю "
                        "краткий, прямой и эстетичный вывод. Без диагнозов. Нужно: 1) что "
                        "видно по человеку, 2) зоны роста, 3) фраза о прохождении проверки "
                        "и ожидании приглашения в закрытый чат. Обращение на 'вы'."
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
            max_tokens=650,
        )
    except Exception:
        return fallback

    required_tail = (
        "\n\nВы прошли проверку. Если вы намерены и дальше идти к субъектности, ожидайте "
        "приглашения в закрытый чат. Оракул еще свяжется с вами.\n\n"
        "Пока вы ожидаете, можете говорить со мной здесь."
    )
    if "прошли проверку" not in conclusion.lower():
        conclusion = conclusion.rstrip() + required_tail
    return conclusion


def build_onboarding_admin_summary(user: User, assessments: list[Assessment]) -> str:
    lines = [
        "Кандидат прошел первичное тестирование ETHOS до конца.",
        "",
        f"Пользователь: @{user.username or 'без username'}",
        f"telegram_id: {user.telegram_id or 'n/a'}",
        f"Индекс субъектности: {user.subjectivity_score}/100",
        f"Статус: {user.status}",
        f"Баланс: {user.token_balance} PsyCoin",
        "",
        "Готов к приглашению в закрытый чат, если администратор подтверждает вручную.",
        "",
        "Краткий профиль:",
    ]
    for index, assessment in enumerate(assessments, start=1):
        lines.extend(
            [
                "",
                f"Кейс {index}:",
                f"- субъектность: {assessment.subjectivity}/100",
                f"- честность: {assessment.honesty}/100",
                f"- эмоциональный суверенитет: {assessment.emotional_sovereignty}/100",
                f"- когнитивное смирение: {assessment.cognitive_humility}/100",
                f"- эмпатия: {assessment.empathy}/100",
                f"- вывод: {assessment.summary[:700]}",
            ]
        )
    return "\n".join(lines)


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
    command = clean.split(maxsplit=1)[0].lower()
    admin_user = is_admin(user)

    if admin_user:
        if session.state != "active":
            session.state = "active"
        if command == "/start":
            return format_admin_help(), "admin_start", 0, None
        admin_reply = await handle_admin_tool_command(db, user, clean)
        if admin_reply is not None:
            return admin_reply, "admin_command", 0, None
        if command == "/case":
            case = await get_random_case(db)
            return (
                format_admin_success("Админ-превью кейса\n\n" + format_case(case)),
                "admin_case_preview",
                0,
                None,
            )
        if command == "/news":
            item = await get_or_create_news_case(db)
            return (
                format_admin_success(
                    "Админ-превью Sentinel Mode\n\n"
                    f"{item.ethical_case}\n\n"
                    f"Источник: {item.source_url}"
                ),
                "admin_news_preview",
                0,
                None,
            )

    if command == "/start":
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
        if len(assessments) >= 3:
            session.state = "active"
            conclusion = await build_onboarding_conclusion(db, user=user, assessments=assessments)
            user.profile_summary = conclusion
            admin_text = build_onboarding_admin_summary(user, assessments)
            session.summary = admin_text
            db.add(
                Summary(
                    session_id=session.id,
                    user_id=user.id,
                    chat_id=user.telegram_id,
                    username=user.username,
                    text=admin_text,
                )
            )
            return conclusion, "onboarding_completed", token_delta, None

        next_step = len(assessments) + 1
        next_case = await get_next_onboarding_case(db, session)
        session.state = f"onboarding:case:{next_case.id}:{next_step}"
        reply = (
            "Ответ принят. Я зафиксировал не только слова, но и способ выбора.\n\n"
            "Следующее испытание.\n\n"
            + format_onboarding_case(next_case, next_step)
        )
        return reply, "onboarding_case_prompt", token_delta, None

    if command == "/help":
        return format_help(), "help", 0, None
    if command in {"/profile", "/status"}:
        return format_profile(user), "profile", 0, None
    if command == "/reset":
        return "Эта команда доступна только администратору.", "forbidden", 0, None
    if command in {"/summary", "/summaries"}:
        if not is_admin(user):
            return "Эта команда доступна только администратору.", "forbidden", 0, None
        summaries = await create_due_summaries(db, older_than_minutes=60)
        if not summaries:
            return (
                format_admin_success("Новых завершенных бесед для summary пока нет."),
                "admin_summary_empty",
                0,
                None,
            )
        return (
            format_admin_success(
                "Созданы новые summary:\n\n"
                + "\n\n".join(
                    f"@{s.username or 'без username'}\n{s.text[:1200]}" for s in summaries[:5]
                )
            ),
            "admin_summary",
            0,
            None,
        )
    if command == "/case":
        case = await get_random_case(db)
        session.state = f"case:{case.id}:1"
        return format_case(case), "case_prompt", 0, None
    if command == "/news":
        item = await get_or_create_news_case(db)
        session.state = f"news:{item.id}:1"
        return (
            "Sentinel Mode\n\n"
            f"{item.ethical_case}\n\n"
            "Займи позицию: что здесь требует ответственности, где возможна манипуляция, "
            "и какой выбор сохранит достоинство?",
            "news_prompt",
            0,
            None,
        )
    if command == "/battle":
        parts = clean.split(maxsplit=1)
        topic = parts[1].strip() if len(parts) > 1 else None
        if topic and not is_admin(user):
            has_privilege = await user_owns_item_type(db, user, "privilege_custom_battle_topic")
            if not has_privilege:
                return (
                    "Своя тема баттла — платная привилегия. Купите в /shop предмет "
                    "«🎙 Право своей темы баттла» или запустите /battle без темы: "
                    "тогда тему предложит Оракул.",
                    "battle_topic_locked",
                    0,
                    None,
                )
        battle = await create_battle(db, user=user, chat_id=chat_id, topic=topic)
        location = "группе" if chat_type in {"group", "supergroup"} else "личном чате"
        return (
            "Баттл открыт.\n\n"
            f"ID: {battle.id}\n"
            f"Режим: {location}\n\n"
            f"Тема: {battle.topic}\n\n"
            "Второй участник входит командой /joinbattle. После обмена аргументами "
            "завершите командой /finishbattle. Ставка: 1 псикоин.",
            "battle_waiting",
            0,
            None,
        )
    if command == "/joinbattle":
        _, message = await join_waiting_battle(db, user=user, chat_id=chat_id)
        return message, "battle_join", 0, None
    if command == "/finishbattle":
        _, message, token_delta = await finish_active_battle(db, chat_id=chat_id)
        return message, "battle_finished", token_delta, None
    if command == "/shop":
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
                "Позиция принята. Второй слой: отдели факт от реакции.\n\n"
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

    if chat_type in {"group", "supergroup"}:
        active_battle = await get_latest_battle(db, chat_id=chat_id, statuses={"active"})
        if active_battle is not None:
            return "Аргумент зафиксирован для текущего баттла.", "battle_argument", 0, None
        return (
            "В группе я реагирую на команды: /battle, /joinbattle, /finishbattle, /news, /case.",
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
