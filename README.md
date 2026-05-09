# Oracle AI Backend

Backend MVP для Telegram-платформы **Оракул ИИ**.

## Что уже заложено

- FastAPI API
- PostgreSQL
- SQLAlchemy async
- Alembic migrations
- Docker Compose
- базовые сущности: users, sessions, messages, cases, assessments, token ledger
- HTTP API, который позже сможет дергать n8n

## Быстрый старт

Самый простой путь — через Docker:

```bash
docker compose up --build
```

API откроется тут:

```text
http://localhost:8000/docs
```

Локальный запуск без Docker требует Python 3.11+:

```bash
cp .env.example .env
docker compose up -d db
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

## Docker-старт

```bash
cp .env.example .env
docker compose up --build
```

## Первые ручки для n8n

Сохранить пользователя:

```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":123,"username":"test","first_name":"Denis"}'
```

Сохранить сообщение и получить черновой ответ:

```bash
curl -X POST http://localhost:8000/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":123,"username":"test","text":"Мне тревожно сегодня"}'
```

Создать кейс:

```bash
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{"title":"Первый выбор","category":"ethics","difficulty":1,"prompt":"Что вы делаете, если видите несправедливость, но вмешательство может навредить вам?"}'
```

Оценить текст:

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":123,"source":"manual","text":"Я сомневаюсь, но готов признать ошибку и подумать о последствиях."}'
```

Принять Telegram update почти напрямую:

```bash
curl -X POST http://localhost:8000/api/v1/telegram/webhook \
  -H "Content-Type: application/json" \
  -d '{"update_id":1,"message":{"chat":{"id":123,"username":"test","first_name":"Denis"},"text":"Привет"}}'
```

## Команды Telegram MVP

- `/start` — старт и idle-режим поддержки.
- `/help` — список команд.
- `/case` — этический кейс с AI-разбором и токенами.
- `/news` — Sentinel Mode: новостной этический кейс с AI-разбором и токенами.
- `/profile` — статус, индекс рефлексии, баланс токенов.
- `/battle [тема]` — создает заготовку баттла в базе. В группе сохраняет `telegram_chat_id`.
- `/shop` — плейсхолдер маркетплейса collectibles.
- `/buy 1` — тестовая покупка за токены.
- `/summary` — ручная admin-команда для `medsi_children`.

Админ сейчас задан по Telegram ID:

```text
7659888703
```

## Mini App Магазина

Локальная веб-витрина магазина:

```text
http://localhost:8000/app/shop?telegram_id=7659888703
```

API магазина:

```text
GET  /api/v1/marketplace/state?telegram_id=7659888703
POST /api/v1/marketplace/buy
```

Для настоящего Telegram Mini App понадобится публичный HTTPS URL. Варианты:

- временно открыть backend через HTTPS-туннель;
- позже выложить frontend на GitHub Pages/Vercel/Netlify;
- backend оставить на хостинге и подключить проверку Telegram WebApp-подписи.

## Summary Админу

Backend закрывает сессии, где пользователь молчит больше 60 минут, и создает summary.
Отдельный n8n workflow `Оракул ИИ - Summary админу` каждые 10 минут забирает новые summary:

```text
GET /api/v1/admin/due-summaries
```

После отправки админу workflow помечает их отправленными:

```text
POST /api/v1/admin/summaries/{summary_id}/sent
```

## Основная идея архитектуры

n8n пока остается слоем автоматизации: Telegram webhook, расписания, уведомления.
Backend становится ядром: хранит данные, принимает сообщения, оценивает ответы, ведет профиль и баллы.

Позже Telegram можно полностью перенести в backend.
