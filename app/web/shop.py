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
  <title>PsyCoin Shop</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #090b0e;
      color: #edf2ee;
      --panel: #101417;
      --panel-2: #151a1d;
      --line: #293137;
      --text-soft: #aeb9b4;
      --coin: #d8b76f;
      --mint: #62d69b;
      --rose: #c46a78;
      --violet: #8b7cff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(180deg, rgba(9, 11, 14, .95), rgba(13, 17, 15, .98)),
        repeating-linear-gradient(90deg, rgba(255,255,255,.035) 0 1px, transparent 1px 48px),
        repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0 1px, transparent 1px 48px);
      color: #edf2ee;
      overflow-x: hidden;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        radial-gradient(circle at 20% 18%, rgba(216,183,111,.34) 0 1px, transparent 1.5px),
        radial-gradient(circle at 78% 22%, rgba(98,214,155,.32) 0 1px, transparent 1.5px),
        radial-gradient(circle at 62% 70%, rgba(196,106,120,.28) 0 1px, transparent 1.5px),
        radial-gradient(circle at 35% 82%, rgba(139,124,255,.28) 0 1px, transparent 1.5px);
      background-size: 220px 220px, 260px 260px, 310px 310px, 280px 280px;
      animation: drift 22s linear infinite;
      opacity: .55;
    }
    @keyframes drift {
      from { transform: translate3d(0, 0, 0); }
      to { transform: translate3d(-36px, 28px, 0); }
    }
    main {
      width: min(980px, 100%);
      margin: 0 auto;
      padding: 18px;
      position: relative;
    }
    header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      align-items: start;
      padding: 8px 0 14px;
    }
    h1 {
      font-size: clamp(28px, 7vw, 48px);
      line-height: .96;
      margin: 0 0 8px;
      letter-spacing: 0;
    }
    h2 {
      font-size: 17px;
      line-height: 1.2;
      margin: 0;
      letter-spacing: 0;
    }
    .muted {
      color: var(--text-soft);
      margin: 0;
      line-height: 1.45;
      max-width: 620px;
    }
    .balance {
      min-width: 154px;
      padding: 12px;
      background: rgba(16, 20, 23, .86);
      border: 1px solid var(--line);
      border-radius: 8px;
      text-align: right;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.05);
    }
    .balance span {
      display: block;
      color: var(--text-soft);
      font-size: 12px;
      margin-bottom: 4px;
    }
    .balance strong {
      color: var(--coin);
      font-size: 20px;
      white-space: nowrap;
    }
    .test-id {
      display: grid;
      grid-template-columns: 160px 1fr;
      gap: 10px;
      align-items: center;
      margin: 4px 0 14px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(16, 20, 23, .62);
    }
    label { color: var(--text-soft); font-size: 13px; }
    input {
      width: 100%;
      min-height: 42px;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid #354047;
      background: #090b0e;
      color: #edf2ee;
      outline: none;
    }
    input:focus { border-color: var(--mint); }
    .tabs {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin: 14px 0;
    }
    .tab, .buy {
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #12171a;
      color: #dce5df;
      font-weight: 800;
      cursor: pointer;
      transition: transform .16s ease, border-color .16s ease, background .16s ease;
    }
    .tab:hover, .buy:hover { transform: translateY(-1px); border-color: #526067; }
    .tab.active {
      color: #07110c;
      background: var(--mint);
      border-color: var(--mint);
    }
    .notice {
      min-height: 22px;
      color: var(--coin);
      white-space: pre-wrap;
      line-height: 1.35;
      margin: 10px 0 12px;
    }
    .panel { display: none; }
    .panel.active { display: block; }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .item {
      min-height: 184px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(18, 23, 26, .92);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.05);
      position: relative;
      overflow: hidden;
    }
    .item-media {
      aspect-ratio: 1 / 1;
      width: 88px;
      min-width: 88px;
      border-radius: 8px;
      border: 1px solid #313a40;
      background:
        radial-gradient(circle at 30% 30%, rgba(216,183,111,.22), transparent 55%),
        linear-gradient(180deg, #14191c, #0f1316);
      object-fit: cover;
      overflow: hidden;
      position: relative;
      z-index: 1;
    }
    .item-media.sphere {
      animation: spherePulse 2.8s ease-in-out infinite;
      box-shadow:
        0 0 0 0 rgba(216,183,111,.18),
        0 0 24px rgba(98,214,155,.16);
    }
    @keyframes spherePulse {
      0%, 100% {
        transform: scale(1);
        box-shadow:
          0 0 0 0 rgba(216,183,111,.16),
          0 0 24px rgba(98,214,155,.14);
      }
      50% {
        transform: scale(1.04);
        box-shadow:
          0 0 0 12px rgba(216,183,111,0),
          0 0 34px rgba(98,214,155,.24);
      }
    }
    .item::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(
        120deg,
        transparent 0 35%,
        rgba(255,255,255,.06) 50%,
        transparent 65% 100%
      );
      transform: translateX(-120%);
      animation: sheen 7s ease-in-out infinite;
      pointer-events: none;
    }
    @keyframes sheen {
      0%, 68% { transform: translateX(-120%); }
      82%, 100% { transform: translateX(120%); }
    }
    .item-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      position: relative;
      z-index: 1;
    }
    .item-head {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      position: relative;
      z-index: 1;
    }
    .item-copy {
      display: grid;
      gap: 8px;
      min-width: 0;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid #3a464c;
      color: #d7dfda;
      font-size: 12px;
      white-space: nowrap;
      background: #0c1012;
    }
    .badge.recommendation { border-color: rgba(98,214,155,.55); color: var(--mint); }
    .badge.privilege { border-color: rgba(139,124,255,.55); color: #c7c0ff; }
    .badge.collectible { border-color: rgba(216,183,111,.55); color: var(--coin); }
    .item p {
      color: #bac5bf;
      margin: 0;
      line-height: 1.42;
      position: relative;
      z-index: 1;
    }
    .price {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--coin);
      font-weight: 900;
      white-space: nowrap;
      position: relative;
      z-index: 1;
    }
    .coin-icon {
      width: 18px;
      height: 18px;
      object-fit: contain;
      flex: 0 0 18px;
    }
    .buy {
      width: 100%;
      background: #1a221c;
      color: var(--mint);
      border-color: rgba(98,214,155,.55);
      position: relative;
      z-index: 1;
    }
    .buy:disabled { opacity: .45; cursor: default; transform: none; }
    .empty {
      border: 1px dashed #38444b;
      border-radius: 8px;
      padding: 18px;
      color: var(--text-soft);
      background: rgba(16, 20, 23, .7);
    }
    .item-meta {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }
    .profile {
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(18, 23, 26, .92);
    }
    .profile-line {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid #222b30;
    }
    .profile-line:last-child { border-bottom: 0; }
    .profile-line span { color: var(--text-soft); }
    .profile-line strong { text-align: right; }
    @media (max-width: 680px) {
      main { padding: 14px; }
      header { grid-template-columns: 1fr; }
      .balance { text-align: left; width: 100%; }
      .test-id { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      .tabs { gap: 6px; }
      .tab { font-size: 13px; padding-inline: 6px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>PsyCoin Shop</h1>
        <p class="muted">
          Коллекционные предметы, привилегии баттлов и персональные рекомендации ETHOS.
        </p>
      </div>
      <div class="balance"><span>Баланс</span><strong id="balance">...</strong></div>
    </header>

    <div class="test-id">
      <label for="telegramId">Telegram ID</label>
      <input id="telegramId" inputmode="numeric" placeholder="7659888703" />
    </div>

    <nav class="tabs" aria-label="Разделы магазина">
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
      <div class="profile">
        <div class="profile-line"><span>Telegram ID</span><strong id="profileId">...</strong></div>
        <div class="profile-line"><span>Статус</span><strong id="profileStatus">...</strong></div>
        <div class="profile-line"><span>Индекс</span><strong id="profileScore">...</strong></div>
        <div class="profile-line"><span>Баланс</span><strong id="profileBalance">...</strong></div>
        <p class="muted" id="profileSummary"></p>
      </div>
    </section>
  </main>

  <script>
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();

    const qs = new URLSearchParams(location.search);
    const input = document.getElementById('telegramId');
    const balance = document.getElementById('balance');
    const profileId = document.getElementById('profileId');
    const profileStatus = document.getElementById('profileStatus');
    const profileScore = document.getElementById('profileScore');
    const profileBalance = document.getElementById('profileBalance');
    const profileSummary = document.getElementById('profileSummary');
    const itemsBox = document.getElementById('items');
    const purchasesBox = document.getElementById('purchases');
    const notice = document.getElementById('notice');

    input.value = qs.get('telegram_id') || tg?.initDataUnsafe?.user?.id || '';

    const statusLabels = {
      object: 'Объект',
      seeker: 'Соискатель',
      faithful: 'Верный',
      keeper: 'Хранитель',
      sighted: 'Зрячий',
      subject: 'Субъект'
    };

    function escapeHTML(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      }[char]));
    }

    function typeLabel(type) {
      if (type === 'wisdom_sphere') return ['recommendation', 'Сфера'];
      if (type.startsWith('recommendation_')) return ['recommendation', 'Рекомендация'];
      if (type.startsWith('privilege_')) return ['privilege', 'Привилегия'];
      return ['collectible', 'Коллекция'];
    }

    function buyLabel(type) {
      return type === 'wisdom_sphere' ? 'Узнать о себе' : 'Купить';
    }

    function coinMarkup(iconUrl, amount) {
      return `
        <span class="price">
          <img class="coin-icon" src="${escapeHTML(iconUrl)}" alt="PsyCoin" />
          ${escapeHTML(amount)}
        </span>
      `;
    }

    function id() { return input.value.trim(); }

    async function load() {
      if (!id()) {
        balance.textContent = '...';
        notice.textContent = 'Откройте магазин из Telegram или введите ID для локального теста.';
        return;
      }
      notice.textContent = '';
      const res = await fetch(`/api/v1/marketplace/state?telegram_id=${encodeURIComponent(id())}`);
      if (!res.ok) {
        balance.textContent = '0';
        notice.textContent = 'Пользователь не найден. Сначала напишите боту /start.';
        itemsBox.innerHTML = '';
        purchasesBox.innerHTML = '';
        return;
      }
      const data = await res.json();
      balance.textContent = `${data.token_balance} PC`;
      profileId.textContent = data.telegram_id;
      profileStatus.textContent = statusLabels[data.status] || data.status;
      profileScore.textContent = `${data.subjectivity_score}/100`;
      profileBalance.textContent = `${data.token_balance} псикоинов`;
      profileSummary.textContent = data.profile_summary || 'Портрет еще формируется.';

      itemsBox.innerHTML = data.items.map(item => {
        const [kind, label] = typeLabel(item.item_type);
        const disabled = data.token_balance < item.price_tokens ? 'disabled' : '';
        return `
          <article class="item">
            <div class="item-head">
              <img
                class="item-media ${item.item_type === 'wisdom_sphere' ? 'sphere' : ''}"
                src="${escapeHTML(item.image_url)}"
                alt="${escapeHTML(item.title)}"
              />
              <div class="item-copy">
                <div class="item-top">
                  <h2>${escapeHTML(item.index)}. ${escapeHTML(item.title)}</h2>
                  <span class="badge ${kind}">${label}</span>
                </div>
                <p>${escapeHTML(item.description)}</p>
              </div>
            </div>
            <div class="item-meta">
              ${coinMarkup(item.currency_icon_url, item.price_tokens)}
              <button
                class="buy"
                ${disabled}
                onclick="buy(${item.index})"
              >${buyLabel(item.item_type)}</button>
            </div>
          </article>
        `;
      }).join('');

      purchasesBox.innerHTML = data.purchases.length ? data.purchases.map(p => {
        const [kind, label] = typeLabel(p.item_type);
        return `
          <article class="item">
            <div class="item-head">
              <img
                class="item-media ${p.item_type === 'wisdom_sphere' ? 'sphere' : ''}"
                src="${escapeHTML(p.image_url)}"
                alt="${escapeHTML(p.title)}"
              />
              <div class="item-copy">
                <div class="item-top">
                  <h2>${escapeHTML(p.title)}</h2>
                  <span class="badge ${kind}">${label}</span>
                </div>
                <p>Куплено за ${coinMarkup(p.currency_icon_url, p.price_tokens)}</p>
              </div>
            </div>
          </article>
        `;
      }).join('') : '<div class="empty">Инвентарь пуст.</div>';
    }

    async function buy(index) {
      notice.textContent = 'Оформляю покупку...';
      const res = await fetch('/api/v1/marketplace/buy', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({telegram_id: Number(id()), item_index: index})
      });
      const data = await res.json();
      notice.textContent = data.message || 'Готово.';
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
