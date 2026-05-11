from __future__ import annotations

import httpx

from app.core.config import settings
from app.services.admins import admin_ids

PRIVATE_COMMANDS = [
    {"command": "start", "description": "Начать путь ETHOS"},
]

GROUP_COMMANDS = [
    {"command": "battle", "description": "Открыть психологический баттл"},
    {"command": "battlefee", "description": "Выбрать уровень баттла"},
    {"command": "joinbattle", "description": "Войти в открытый баттл"},
    {"command": "finishbattle", "description": "Завершить баттл"},
    {"command": "case", "description": "Получить ETHOS-кейс"},
    {"command": "news", "description": "Разобрать новость как этический кейс"},
    {"command": "finishdiscussion", "description": "Завершить разбор"},
]

ADMIN_COMMANDS = [
    {"command": "start", "description": "Админ-панель"},
    {"command": "admin", "description": "Показать админ-команды"},
    {"command": "users", "description": "Последние пользователи"},
    {"command": "user", "description": "Карточка пользователя"},
    {"command": "reset", "description": "Полностью обнулить профиль"},
    {"command": "addcoins", "description": "Начислить PsyCoin"},
    {"command": "grant", "description": "Изменить баланс PsyCoin"},
    {"command": "setscore", "description": "Задать индекс субъектности"},
    {"command": "setstatus", "description": "Задать статус"},
    {"command": "setlifecycle", "description": "Задать этап доступа"},
    {"command": "close", "description": "Закрыть активные сессии"},
    {"command": "shoplink", "description": "Ссылка на mini-app магазина"},
    {"command": "withdrawals", "description": "Заявки на вывод Stars"},
    {"command": "withdrawdone", "description": "Отметить вывод Stars"},
    {"command": "synccommands", "description": "Обновить меню команд"},
]


async def sync_telegram_bot_commands() -> str:
    token = settings.telegram_bot_token.strip()
    if not token:
        return (
            "TELEGRAM_BOT_TOKEN не задан в переменных backend. "
            "Добавьте токен бота в Railway и повторите /synccommands."
        )

    commands_url = f"https://api.telegram.org/bot{token}/setMyCommands"
    menu_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"
    payloads = [
        {
            "commands": PRIVATE_COMMANDS,
            "scope": {"type": "default"},
        },
        {
            "commands": PRIVATE_COMMANDS,
            "scope": {"type": "all_private_chats"},
        },
        {
            "commands": GROUP_COMMANDS,
            "scope": {"type": "all_group_chats"},
        },
    ]
    for admin_id in admin_ids():
        payloads.append(
            {
                "commands": ADMIN_COMMANDS,
                "scope": {"type": "chat", "chat_id": admin_id},
            }
        )

    async with httpx.AsyncClient(timeout=12) as client:
        for payload in payloads:
            response = await client.post(commands_url, json=payload)
            data = response.json()
            if response.status_code >= 400 or not data.get("ok"):
                description = data.get("description") or response.text
                return f"Telegram не принял меню команд: {description}"
        menu_status = "Mini-app кнопка не обновлялась: PUBLIC_WEBAPP_URL должен быть HTTPS."
        if settings.public_webapp_url.startswith("https://"):
            response = await client.post(
                menu_url,
                json={
                    "menu_button": {
                        "type": "web_app",
                        "text": "ETHOS",
                        "web_app": {"url": settings.public_webapp_url},
                    }
                },
            )
            data = response.json()
            if response.status_code >= 400 or not data.get("ok"):
                description = data.get("description") or response.text
                return f"Telegram не принял mini-app кнопку: {description}"
            menu_status = "Mini-app кнопка ETHOS обновлена."

    return (
        "Меню команд Telegram обновлено.\n\n"
        "Личные чаты: только /start.\n"
        "Группы: /battle, /battlefee, /joinbattle, /finishbattle, /case, /news, "
        "/finishdiscussion.\n"
        "Админ: полный набор команд.\n"
        f"{menu_status}"
    )
