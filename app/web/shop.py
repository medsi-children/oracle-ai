from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/app/shop", response_class=HTMLResponse)
async def shop_app() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Oracle AI Shop</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      color-scheme: light dark;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f1417;
      color: #eef3f1;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: #0f1417; color: #eef3f1; }
    main { max-width: 820px; margin: 0 auto; padding: 18px; }
    header { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; margin-bottom: 16px; }
    h1 { font-size: 26px; line-height: 1.1; margin: 0 0 6px; }
    h2 { font-size: 18px; margin: 0; }
    .muted { color: #aab7b2; margin: 0; line-height: 1.35; }
    .balance {
      min-width: 132px;
      padding: 11px 12px;
      background: #182126;
      border: 1px solid #2a383f;
      border-radius: 8px;
      text-align: right;
      font-weight: 700;
    }
    .tabs { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 14px 0; }
    .tab {
      border: 1px solid #2a383f;
      border-radius: 8px;
      padding: 10px;
      background: #121a1e;
      color: #c9d4d0;
      font-weight: 700;
      cursor: pointer;
    }
    .tab.active { background: #69d2a0; color: #07130d; border-color: #69d2a0; }
    .panel { display: none; }
    .panel.active { display: block; }
    .test-id { margin: 10px 0 16px; }
    label { display: block; color: #aab7b2; font-size: 13px; margin-bottom: 6px; }
    input {
      width: 100%;
      padding: 11px;
      border-radius: 8px;
      border: 1px solid #2a383f;
      background: #0f1417;
      color: #eef3f1;
    }
    .grid { display: grid; gap: 12px; }
    .item {
      border: 1px solid #2a383f;
      background: #151d21;
      border-radius: 8px;
      padding: 14px;
    }
    .item-top { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    .price { color: #8be0b2; font-weight: 800; white-space: nowrap; }
    .item p { color: #b9c4c0; margin: 8px 0 12px; line-height: 1.4; }
    button.buy {
      width: 100%;
      border: 0;
      border-radius: 8px;
      padding: 11px 12px;
      background: #69d2a0;
      color: #07130d;
      font-weight: 800;
      cursor: pointer;
    }
    button.buy:disabled { opacity: .45; cursor: default; }
    .notice { min-height: 22px; color: #ffd27a; margin: 10px 0; }
    .empty { border: 1px dashed #2a383f; border-radius: 8px; padding: 18px; color: #aab7b2; }
    .profile-line { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #243138; }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Oracle AI Shop</h1>
        <p class="muted">Collectibles-витрина Оракула ИИ. MVP будущего магазина статусов и наград.</p>
      </div>
      <div class="balance" id="balance">...</div>
    </header>
    <div class="test-id">
      <label>Telegram ID для локального теста</label>
      <input id="telegramId" placeholder="например 7659888703" />
    </div>
    <nav class="tabs">
      <button class="tab active" data-tab="shop">Магазин</button>
      <button class="tab" data-tab="inventory">Инвентарь</button>
      <button class="tab" data-tab="profile">Профиль</button>
    </nav>
    <div class="notice" id="notice"></div>
    <section class="panel active" id="shopPanel">
      <div class="grid" id="items"></div>
    </section>
    <section class="panel" id="inventoryPanel">
      <div class="grid" id="purchases"></div>
    </section>
    <section class="panel" id="profilePanel">
      <div class="item">
        <h2>Профиль</h2>
        <div class="profile-line"><span>Telegram ID</span><strong id="profileId">...</strong></div>
        <div class="profile-line"><span>Баланс</span><strong id="profileBalance">...</strong></div>
        <p class="muted">Позже здесь появятся статус, бейджи, история роста и доступные привилегии.</p>
      </div>
    </section>
  </main>
  <script>
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    const qs = new URLSearchParams(location.search);
    const input = document.getElementById('telegramId');
    input.value = qs.get('telegram_id') || tg?.initDataUnsafe?.user?.id || '';
    const balance = document.getElementById('balance');
    const profileId = document.getElementById('profileId');
    const profileBalance = document.getElementById('profileBalance');
    const itemsBox = document.getElementById('items');
    const purchasesBox = document.getElementById('purchases');
    const notice = document.getElementById('notice');

    function id() { return input.value.trim(); }

    async function load() {
      if (!id()) {
        balance.textContent = 'Введите Telegram ID или откройте приложение из Telegram.';
        return;
      }
      notice.textContent = '';
      const res = await fetch(`/api/v1/marketplace/state?telegram_id=${encodeURIComponent(id())}`);
      if (!res.ok) {
        balance.textContent = 'Пользователь не найден. Сначала напишите боту /start.';
        itemsBox.innerHTML = '';
        purchasesBox.innerHTML = '';
        return;
      }
      const data = await res.json();
      balance.textContent = `Баланс: ${data.token_balance} токенов`;
      profileId.textContent = data.telegram_id;
      profileBalance.textContent = `${data.token_balance} токенов`;
      itemsBox.innerHTML = data.items.map(item => `
        <article class="item">
          <div class="item-top">
            <h2>${item.index}. ${item.title}</h2>
            <div class="price">${item.price_tokens}</div>
          </div>
          <p>${item.description}</p>
          <button class="buy" onclick="buy(${item.index})">Купить</button>
        </article>
      `).join('');
      purchasesBox.innerHTML = data.purchases.length ? data.purchases.map(p => `
        <article class="item"><h2>${p.title}</h2><p>Куплено за ${p.price_tokens} токенов</p></article>
      `).join('') : '<div class="empty">Пока покупок нет. Пройдите /case или /news, заработайте токены и возвращайтесь.</div>';
    }

    async function buy(index) {
      notice.textContent = 'Покупаю...';
      const res = await fetch('/api/v1/marketplace/buy', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({telegram_id: Number(id()), item_index: index})
      });
      const data = await res.json();
      notice.textContent = data.message || 'Готово';
      await load();
    }

    input.addEventListener('change', load);
    document.querySelectorAll('.tab').forEach(button => {
      button.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));
        button.classList.add('active');
        document.getElementById(button.dataset.tab + 'Panel').classList.add('active');
      });
    });
    load();
  </script>
</body>
</html>"""
