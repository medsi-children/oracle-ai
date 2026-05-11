# Oracle AI Backend

Backend MVP для Telegram-платформы **Оракул ИИ**.

## Что уже заложено

- FastAPI API
- PostgreSQL
- SQLAlchemy async
- Alembic migrations
- Docker Compose
- базовые сущности: users, sessions, messages, cases, assessments, token ledger
- ETHOS first-contact flow и скрытая аналитика ответа
- магазин псикоинов: трофеи, привилегии, персональные рекомендации
- групповые баттлы со ставкой 1 псикоин
- коллекционные трофеи с мягким баффом в баттлах, максимум +18% к базовой оценке
- стартовая калибровка индекса после ETHOS-теста: даже сильный участник не начинает с 100/100
- прямой Telegram webhook без n8n

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

## Первые ручки

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

Прямой Telegram webhook для production:

```text
POST /api/v1/telegram/direct-webhook
```

Админ включает его командой:

```text
/syncwebhook
```

После этого n8n можно выключить.

## Команды Telegram MVP

- `/start` — протокол первого контакта ETHOS и калибровочный кейс №0.
- `/help` — список команд.
- `/case` — этический кейс с уточнением, AI-разбором и псикоинами.
- `/news` — Sentinel Mode: реальная новость через RSS как этический кейс.
- `/profile` — статус, индекс субъектности, баланс псикоинов.
- `/battle` — создает баттл на тему Оракула.
- `/battle [тема]` — баттл на свою тему, если куплена привилегия.
- `/joinbattle` — присоединиться вторым участником.
- `/finishbattle` — завершить баттл, распределить ставку и бонусы роста.
- В финальном счете баттла показывается базовая оценка и бафф от самого сильного купленного трофея.
- `/shop` — магазин псикоинов.
- `/buy 1` — покупка предмета, привилегии или персональной рекомендации.
Для админа доступны дополнительные команды:

- `/admin` — список админ-команд.
- `/users [число]` — последние пользователи.
- `/user @username` — карточка пользователя и счетчики.
- `/reset @username` — полный reset профиля пользователя.
- `/grant @username 10 причина` — изменить баланс псикоинов.
- `/setscore @username 50` — задать индекс субъектности.
- `/setstatus @username object` — задать статус.
- `/setlifecycle @username follower` — задать внутренний этап доступа.
- `/close @username` — закрыть активные сессии пользователя.
- `/shoplink @username` — ссылка на mini-app магазина.
- `/synccommands` — обновить меню команд и mini-app кнопку.
- `/syncwebhook` — подключить Telegram напрямую к backend.
- `/webhookinfo` — проверить текущий Telegram webhook.

Для `/start` backend сам проигрывает `intro_animation`: отправляет первую строку как
временное сообщение, редактирует его по шагам, удаляет и отправляет финальный `reply`.

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

Для ссылки на закрытую группу после первого тестирования задайте:

```env
CLOSED_GROUP_INVITE_URL=https://t.me/+...
```

Для настоящего Telegram Mini App понадобится публичный HTTPS URL. Варианты:

- временно открыть backend через HTTPS-туннель;
- позже выложить frontend на GitHub Pages/Vercel/Netlify;
- backend оставить на хостинге и подключить проверку Telegram WebApp-подписи.

## Основная идея архитектуры

Backend теперь сам принимает Telegram webhook, отправляет сообщения, inline-кнопки,
intro-анимацию и платежные ответы Telegram Stars. n8n больше не нужен для production-бота и
может оставаться только как legacy fallback.
