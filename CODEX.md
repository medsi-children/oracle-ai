# Codex handoff

Этот файл нужен для нового чата Codex, чтобы быстро продолжить работу с проектом.
Архитектуру не пересказывать: актуальную структуру проще смотреть по коду.

## Проект

- Локальная папка: `/Users/ori.space.cat/Оракул ИИ`
- GitHub: `https://github.com/medsi-children/oracle-ai`
- Git remote:
  - fetch: `https://github.com/medsi-children/oracle-ai.git`
  - push: `https://github.com/medsi-children/oracle-ai.git`
- Основная ветка: `main`
- Перед началом работы обычно делать:
  - `git status --short --branch`
  - `git pull --ff-only`
- Пушить изменения обратно в `origin main`, если пользователь просит "пушим" или явно просит выложить изменения.

## Хостинг и окружение

- Проект задеплоен на Railway.
- Все production-переменные окружения задаются прямо в Railway.
- Секреты в репозиторий не записывать.
- Пример списка переменных лежит в `.env.example`.

Ключевые переменные:

- `DATABASE_URL` — async Postgres connection string для приложения.
- `SYNC_DATABASE_URL` — sync Postgres connection string для Alembic/миграций.
- `OPENROUTER_API_KEY` — ключ OpenRouter.
- `OPENROUTER_MODEL` — модель OpenRouter.
- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота.
- `TELEGRAM_WEBHOOK_SECRET_TOKEN` — секрет direct webhook Telegram.
- `ADMIN_TELEGRAM_USERNAME` — Telegram username админа.
- `ADMIN_TELEGRAM_IDS` — Telegram ID админов.
- `PUBLIC_WEBAPP_URL` — публичный HTTPS URL mini-app, используется и для Telegram web_app кнопок.

## База данных

- Production база данных: PostgreSQL в Railway.
- Подключение идет через `DATABASE_URL` и `SYNC_DATABASE_URL`.
- Миграции: Alembic.
- Dockerfile при старте выполняет `alembic upgrade head`, потом запускает `uvicorn`.

## Нейронка

- LLM-провайдер: OpenRouter.
- Основная точка вызова в коде: `app/services/llm.py`.
- Ключ и модель берутся из Railway variables:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL`
- Если OpenRouter недоступен или ключ пустой, часть функций уходит в fallback-логику, где она предусмотрена.

## Telegram и mini-app

- Telegram-бот работает через backend webhook.
- Direct webhook URL строится из `PUBLIC_WEBAPP_URL` и `settings.api_v1_prefix`.
- Mini-app кнопка Telegram использует `PUBLIC_WEBAPP_URL`.
- Синхронизация команд/кнопки есть в сервисах Telegram, смотри `app/services/telegram_menu.py` и `app/services/telegram_delivery.py`.

## Практические правила для следующего Codex

- Не хранить токены, ключи OpenRouter, Telegram bot token или Railway/Postgres secrets в файлах репозитория.
- Если нужно поменять production-переменные, делать это в Railway, а не в коде.
- Если пользователь просит "подтяни последнюю версию", делать `git pull --ff-only` после проверки `git status`.
- Если пользователь просит "пушим", проверить diff, сделать осмысленный commit и `git push origin main`, если работа идет прямо в `main`.
- Если есть локальные изменения пользователя, не перетирать их: сначала разобраться через `git status`, `git diff`, при необходимости использовать autostash или спросить.
- Для проверки Python-кода учитывать, что проект требует Python `>=3.11`; локальный системный `python3` может быть старым.
