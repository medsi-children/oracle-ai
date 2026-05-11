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
  <title>Магазин</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      color-scheme: dark;
      font-family: "Avenir Next", "Helvetica Neue", system-ui, sans-serif;
      --bg-1: #130f15;
      --bg-2: #1b1318;
      --panel: rgba(31, 21, 28, .78);
      --panel-strong: rgba(39, 26, 35, .92);
      --line: rgba(255, 214, 228, .12);
      --text: #f8eef2;
      --text-soft: #cab8c0;
      --accent: #f6b8ca;
      --accent-strong: #ff8fb1;
      --accent-deep: #7e4358;
      --coin: #ffd8a1;
      --shadow: 0 22px 60px rgba(0, 0, 0, .35);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at top, rgba(255, 143, 177, .16), transparent 28%),
        radial-gradient(circle at 78% 22%, rgba(246, 184, 202, .12), transparent 24%),
        linear-gradient(180deg, var(--bg-1), #0d0b10 74%);
      overflow-x: hidden;
    }
    body::before,
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
    }
    body::before {
      background:
        radial-gradient(circle at 20% 18%, rgba(255,255,255,.11) 0 1px, transparent 1.5px),
        radial-gradient(circle at 72% 28%, rgba(255,255,255,.09) 0 1px, transparent 1.5px),
        radial-gradient(circle at 38% 76%, rgba(255,255,255,.08) 0 1px, transparent 1.5px);
      background-size: 220px 220px, 290px 290px, 260px 260px;
      animation: drift 26s linear infinite;
      opacity: .5;
    }
    body::after {
      background:
        linear-gradient(120deg, transparent, rgba(255,255,255,.04), transparent);
      transform: translateX(-120%);
      animation: veil 13s ease-in-out infinite;
      opacity: .35;
    }
    @keyframes drift {
      from { transform: translate3d(0, 0, 0); }
      to { transform: translate3d(-28px, 24px, 0); }
    }
    @keyframes veil {
      0%, 70% { transform: translateX(-120%); }
      100% { transform: translateX(120%); }
    }
    main {
      width: min(1080px, 100%);
      margin: 0 auto;
      padding:
        max(34px, calc(env(safe-area-inset-top, 0px) + 26px))
        18px
        28px;
      position: relative;
    }
    header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-areas:
        "hero profile"
        "balance balance";
      gap: 14px 16px;
      align-items: start;
      margin-bottom: 20px;
    }
    .hero {
      grid-area: hero;
      display: grid;
      gap: 8px;
      min-width: 0;
    }
    h1 {
      margin: 0;
      font-size: clamp(32px, 8vw, 56px);
      line-height: .95;
      letter-spacing: 0;
      font-weight: 700;
    }
    .subline {
      margin: 0;
      max-width: 680px;
      color: var(--text-soft);
      line-height: 1.5;
      font-size: 14px;
    }
    .balance {
      grid-area: balance;
      min-width: 170px;
      display: grid;
      gap: 6px;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(44, 28, 38, .9), rgba(21, 15, 20, .96));
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
      color: var(--text);
      text-align: left;
      cursor: pointer;
      font: inherit;
    }
    .balance:hover {
      border-color: rgba(255, 184, 202, .34);
      transform: translateY(-1px);
    }
    .profile-button {
      grid-area: profile;
      width: 48px;
      height: 48px;
      display: grid;
      place-items: center;
      align-self: start;
      justify-self: end;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(44, 28, 38, .9), rgba(21, 15, 20, .96));
      box-shadow: var(--shadow);
      color: #ffe7ef;
      cursor: pointer;
      transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
    }
    .profile-button:hover {
      transform: translateY(-1px);
      border-color: rgba(255, 184, 202, .34);
    }
    .profile-glyph {
      width: 22px;
      height: 22px;
      display: block;
    }
    .profile-glyph path,
    .profile-glyph circle {
      stroke: currentColor;
      stroke-width: 1.8;
      fill: none;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .balance-label {
      color: var(--text-soft);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .balance-value {
      display: inline-flex;
      align-items: center;
      justify-content: flex-start;
      gap: 12px;
      width: 100%;
      font-size: 34px;
      line-height: 1.05;
      font-weight: 800;
      color: var(--text);
    }
    .balance-value .coin-amount {
      display: inline-block;
      line-height: inherit;
    }
    .balance-value .coin-icon {
      width: 40px;
      height: 40px;
      flex-basis: 40px;
    }
    .vip-badge {
      margin-left: auto;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #ffd76a;
      font-size: 34px;
      line-height: 1.05;
      font-weight: 800;
      letter-spacing: 0;
      text-shadow:
        0 0 18px rgba(255, 215, 106, .24),
        0 1px 0 rgba(255, 255, 255, .16);
    }
    .vip-icon {
      width: 40px;
      height: 40px;
      object-fit: contain;
      flex: 0 0 40px;
      opacity: 0;
      transition: opacity .28s ease, transform .28s ease;
    }
    .coin-icon {
      width: 20px;
      height: 20px;
      object-fit: contain;
      flex: 0 0 20px;
      border-radius: 999px;
      opacity: 0;
      transition: opacity .28s ease, transform .28s ease;
    }
    .tabs {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .tab, .buy {
      min-height: 48px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(31, 21, 28, .78);
      color: var(--text);
      font-weight: 700;
      cursor: pointer;
      transition:
        transform .18s ease,
        border-color .18s ease,
        background .18s ease,
        box-shadow .18s ease;
    }
    .tab:hover, .buy:hover {
      transform: translateY(-1px);
      border-color: rgba(255, 184, 202, .32);
      box-shadow: 0 10px 24px rgba(0, 0, 0, .22);
    }
    .tab.active {
      color: #2b1520;
      background: linear-gradient(180deg, var(--accent), var(--accent-strong));
      border-color: rgba(255, 184, 202, .65);
    }
    .notice {
      min-height: 22px;
      margin: 6px 0 16px;
      color: #ffd3df;
      white-space: pre-wrap;
      line-height: 1.42;
    }
    .panel { display: none; }
    .panel.active { display: block; }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .card {
      position: relative;
      overflow: hidden;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(36, 24, 32, .96), rgba(20, 14, 19, .98));
      box-shadow: var(--shadow);
      padding: 18px;
    }
    .card::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(
        140deg,
        transparent 0 45%,
        rgba(255,255,255,.05) 52%,
        transparent 64% 100%
      );
      transform: translateX(-120%);
      animation: sheen 8s ease-in-out infinite;
      pointer-events: none;
    }
    @keyframes sheen {
      0%, 76% { transform: translateX(-120%); }
      100% { transform: translateX(120%); }
    }
    .item {
      min-height: 250px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 14px;
    }
    .item-head {
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 14px;
      align-items: start;
      position: relative;
      z-index: 1;
    }
    .item-media {
      width: 110px;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 18px;
      border: 1px solid rgba(255, 214, 228, .18);
      background:
        radial-gradient(circle at 30% 30%, rgba(255,255,255,.16), transparent 52%),
        linear-gradient(180deg, #2d1b25, #151017);
      box-shadow: 0 18px 30px rgba(0, 0, 0, .28);
      animation: itemPulse 3.8s ease-in-out infinite;
      opacity: 0;
      transition: opacity .34s ease, transform .34s ease;
    }
    @keyframes itemPulse {
      0%, 100% {
        transform: scale(1);
        box-shadow: 0 18px 30px rgba(0, 0, 0, .28);
      }
      50% {
        transform: scale(1.025);
        box-shadow:
          0 0 0 10px rgba(255, 184, 202, 0),
          0 20px 34px rgba(0, 0, 0, .3);
      }
    }
    .item-copy {
      display: grid;
      gap: 10px;
      min-width: 0;
    }
    .item-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }
    h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.18;
      letter-spacing: 0;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255, 214, 228, .16);
      color: #f7d3df;
      font-size: 12px;
      white-space: nowrap;
      background: rgba(255, 255, 255, .03);
    }
    .badge.collectible { color: #ffe1b7; }
    .badge.recommendation { color: #ffd5ef; }
    .badge.privilege { color: #ffd1dc; }
    .badge.owned {
      color: #ffe9b9;
      border-color: rgba(255, 225, 185, .22);
      background: rgba(255, 225, 185, .06);
    }
    .item p, .profile-copy, .premium-copy {
      margin: 0;
      color: var(--text-soft);
      line-height: 1.5;
      position: relative;
      z-index: 1;
    }
    .item-meta {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      position: relative;
      z-index: 1;
    }
    .price {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--coin);
      font-weight: 800;
      white-space: nowrap;
    }
    .buy {
      min-width: 154px;
      padding: 0 18px;
      background: linear-gradient(180deg, rgba(255, 184, 202, .18), rgba(255, 143, 177, .12));
      color: #ffe9f0;
      border-color: rgba(255, 184, 202, .3);
    }
    .buy:disabled {
      opacity: .45;
      cursor: default;
      transform: none;
      box-shadow: none;
    }
    .wisdom-stage {
      min-height: 64vh;
      display: grid;
      place-items: center;
    }
    .wisdom-shell {
      width: min(100%, 560px);
      display: grid;
      gap: 22px;
      justify-items: center;
      text-align: center;
      padding: 30px 20px 26px;
    }
    .sphere-wrap {
      width: min(78vw, 340px);
      aspect-ratio: 1 / 1;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background:
        radial-gradient(circle, rgba(255, 184, 202, .14), rgba(255, 184, 202, 0) 62%);
      animation: aura 4s ease-in-out infinite;
    }
    .sphere-image {
      width: min(74vw, 300px);
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 999px;
      border: 1px solid rgba(255, 214, 228, .22);
      box-shadow:
        0 0 0 0 rgba(255, 184, 202, .2),
        0 0 36px rgba(255, 184, 202, .16),
        0 24px 48px rgba(0, 0, 0, .3);
      animation: spherePulse 2.8s ease-in-out infinite;
      opacity: 0;
      transition: opacity .34s ease, transform .34s ease;
    }
    @keyframes aura {
      0%, 100% { transform: scale(1); opacity: .9; }
      50% { transform: scale(1.06); opacity: 1; }
    }
    @keyframes spherePulse {
      0%, 100% {
        transform: scale(1);
        box-shadow:
          0 0 0 0 rgba(255, 184, 202, .18),
          0 0 36px rgba(255, 184, 202, .16),
          0 24px 48px rgba(0, 0, 0, .3);
      }
      50% {
        transform: scale(1.04);
        box-shadow:
          0 0 0 18px rgba(255, 184, 202, 0),
          0 0 48px rgba(255, 184, 202, .28),
          0 28px 58px rgba(0, 0, 0, .32);
      }
    }
    .wisdom-copy {
      display: grid;
      gap: 10px;
      max-width: 480px;
    }
    .wisdom-copy h2 {
      font-size: clamp(28px, 6vw, 42px);
    }
    .wisdom-buy {
      min-width: 220px;
      justify-self: center;
    }
    .premium-stage, .profile-stage, .wallet-stage {
      display: grid;
      gap: 16px;
    }
    .wallet-shell {
      min-height: 62vh;
      display: grid;
      place-items: center;
      text-align: center;
      gap: 20px;
      padding: 32px 18px;
    }
    .wallet-coin-wrap {
      width: min(66vw, 280px);
      aspect-ratio: 1 / 1;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background:
        radial-gradient(circle, rgba(255, 216, 161, .16), rgba(255, 216, 161, 0) 62%);
      animation: aura 4s ease-in-out infinite;
    }
    .wallet-coin {
      width: min(58vw, 220px);
      aspect-ratio: 1 / 1;
      object-fit: contain;
      border-radius: 999px;
      opacity: 0;
      transition: opacity .34s ease, transform .34s ease;
      animation: spherePulse 2.8s ease-in-out infinite;
    }
    .wallet-amount {
      display: grid;
      gap: 8px;
      justify-items: center;
    }
    .wallet-amount strong {
      font-size: clamp(44px, 13vw, 76px);
      line-height: .95;
      color: var(--coin);
    }
    .wallet-actions {
      width: min(100%, 420px);
      display: grid;
      grid-template-columns: 56px minmax(0, 1fr);
      gap: 10px;
    }
    .icon-buy {
      min-width: 56px;
      padding: 0;
      font-size: 30px;
      line-height: 1;
    }
    .dev-card {
      display: none;
      width: min(100%, 420px);
      border-radius: 18px;
      border: 1px dashed rgba(255, 214, 228, .18);
      color: #ffd3df;
      background: rgba(255, 255, 255, .04);
      padding: 16px;
    }
    .dev-card.visible {
      display: block;
    }
    .premium-card {
      display: grid;
      gap: 18px;
    }
    .premium-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 220px;
      gap: 24px;
      align-items: start;
    }
    .premium-media {
      width: 220px;
      max-width: 100%;
      justify-self: end;
    }
    .profile-card {
      display: grid;
      gap: 18px;
    }
    .profile-status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      width: fit-content;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 184, 202, .09);
      border: 1px solid rgba(255, 184, 202, .18);
      color: #ffd6e5;
      font-size: 13px;
    }
    .profile-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .profile-metric {
      padding: 14px;
      border-radius: 16px;
      border: 1px solid rgba(255, 214, 228, .1);
      background: rgba(255, 255, 255, .03);
    }
    .profile-metric span {
      display: block;
      color: var(--text-soft);
      font-size: 12px;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .profile-metric strong {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 34px;
      line-height: 1.05;
      font-weight: 800;
      color: var(--text);
    }
    #profileBalance {
      display: block;
      width: 100%;
    }
    .profile-balance-value {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: inherit;
      line-height: inherit;
      font-weight: inherit;
      color: var(--text);
    }
    .profile-balance-value .coin-amount {
      display: inline-block;
      font-size: 34px;
      line-height: 1.05;
      font-weight: 800;
      letter-spacing: inherit;
      color: inherit;
    }
    .profile-balance-value .coin-icon {
      width: 24px;
      height: 24px;
      flex-basis: 24px;
    }
    .profile-collectibles {
      display: none;
      gap: 12px;
      padding-top: 4px;
    }
    .profile-collectibles.visible {
      display: grid;
    }
    .profile-collectibles-title {
      color: var(--text-soft);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .profile-collectibles-list {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(116px, 1fr));
      gap: 12px;
    }
    .profile-collectible {
      width: 54px;
      height: 54px;
      object-fit: cover;
      border-radius: 14px;
      border: 1px solid rgba(255, 214, 228, .16);
      background:
        radial-gradient(circle at 30% 30%, rgba(255,255,255,.12), transparent 52%),
        linear-gradient(180deg, #2d1b25, #151017);
      box-shadow: 0 10px 24px rgba(0, 0, 0, .28);
      opacity: 0;
      transition: opacity .28s ease, transform .28s ease;
      animation: itemPulse 4.6s ease-in-out infinite;
    }
    .inventory-tile {
      display: grid;
      justify-items: center;
      gap: 10px;
      padding: 12px 10px;
      border-radius: 16px;
      border: 1px solid rgba(255, 214, 228, .12);
      background: rgba(255, 255, 255, .03);
      text-align: center;
    }
    .inventory-tile span {
      color: var(--text);
      font-size: 13px;
      line-height: 1.3;
    }
    .purchase-overlay {
      position: fixed;
      inset: 0;
      z-index: 30;
      display: none;
      padding: 18px;
      background: rgba(13, 8, 11, .84);
      backdrop-filter: blur(14px);
      place-items: center;
    }
    .purchase-overlay.visible {
      display: grid;
    }
    .purchase-modal {
      width: min(100%, 520px);
      display: grid;
      gap: 18px;
      padding: 28px 22px 22px;
      text-align: center;
    }
    .purchase-modal h2 {
      font-size: clamp(30px, 7vw, 44px);
      line-height: 1.02;
    }
    .purchase-modal p {
      margin: 0;
      color: var(--text-soft);
      line-height: 1.55;
    }
    .purchase-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .loading-image {
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(110deg, rgba(255, 255, 255, .04) 20%, rgba(255, 255, 255, .14) 36%, rgba(255, 255, 255, .04) 52%),
        radial-gradient(circle at 30% 30%, rgba(255,255,255,.08), transparent 52%),
        linear-gradient(180deg, rgba(45, 27, 37, .95), rgba(21, 16, 23, .98));
      background-size: 220% 100%, auto, auto;
      animation:
        imageShimmer 1.8s linear infinite,
        itemPulse 3.8s ease-in-out infinite;
    }
    .coin-icon.loading-image {
      animation: imageShimmer 1.5s linear infinite;
    }
    .sphere-image.loading-image {
      animation:
        imageShimmer 1.8s linear infinite,
        spherePulse 2.8s ease-in-out infinite;
    }
    .image-ready {
      opacity: 1;
    }
    @keyframes imageShimmer {
      0% { background-position: 180% 0, 0 0, 0 0; }
      100% { background-position: -40% 0, 0 0, 0 0; }
    }
    .empty {
      border-radius: 22px;
      border: 1px dashed rgba(255, 214, 228, .16);
      background: rgba(255, 255, 255, .03);
      padding: 22px;
      color: var(--text-soft);
    }
    .locked-view {
      min-height: 100vh;
      display: none;
      place-items: center;
      padding: 28px;
      text-align: center;
      color: var(--text);
      font-size: clamp(28px, 8vw, 58px);
      line-height: 1.08;
      font-weight: 800;
    }
    body.locked main {
      display: none;
    }
    body.locked .locked-view {
      display: grid;
    }
    .entry-view {
      min-height: 100vh;
      display: none;
      place-items: center;
      padding:
        max(34px, calc(env(safe-area-inset-top, 0px) + 28px))
        18px
        28px;
      text-align: center;
      position: relative;
      z-index: 2;
    }
    body.entry main {
      display: none;
    }
    body.entry .entry-view {
      display: grid;
    }
    .entry-shell {
      width: min(100%, 540px);
      display: grid;
      gap: 22px;
      justify-items: center;
    }
    .entry-image-wrap {
      width: min(72vw, 340px);
      aspect-ratio: 1 / 1;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background:
        radial-gradient(circle, rgba(255, 184, 202, .18), rgba(255, 184, 202, 0) 64%);
      animation: aura 3.6s ease-in-out infinite;
    }
    .entry-image {
      width: min(62vw, 260px);
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 30px;
      border: 1px solid rgba(255, 214, 228, .22);
      box-shadow:
        0 0 0 0 rgba(255, 184, 202, .26),
        0 24px 60px rgba(0, 0, 0, .34);
      animation: spherePulse 2.6s ease-in-out infinite;
    }
    .entry-title {
      margin: 0;
      font-size: clamp(34px, 9vw, 64px);
      line-height: .95;
    }
    .entry-price {
      color: var(--coin);
      font-weight: 800;
      font-size: 24px;
    }
    .entry-status {
      min-height: 24px;
      color: var(--text-soft);
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .entry-actions {
      width: min(100%, 420px);
      display: grid;
      gap: 10px;
    }
    .entry-link {
      display: none;
      align-items: center;
      justify-content: center;
      text-decoration: none;
    }
    .entry-link.visible {
      display: inline-flex;
    }
    @media (max-width: 840px) {
      header {
        grid-template-columns: minmax(0, 1fr) auto;
        grid-template-areas:
          "hero profile"
          "balance balance";
      }
      .balance { width: 100%; }
      .grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      .premium-head {
        grid-template-columns: 1fr;
      }
      .premium-media {
        width: min(100%, 220px);
        justify-self: center;
      }
    }
    @media (max-width: 560px) {
      main {
        padding:
          max(34px, calc(env(safe-area-inset-top, 0px) + 26px))
          14px
          24px;
      }
      .item-head {
        grid-template-columns: 1fr;
      }
      .item-media {
        width: 100%;
        max-width: 160px;
      }
      .item-meta {
        flex-direction: column;
        align-items: stretch;
      }
      .buy {
        width: 100%;
      }
      .tabs {
        gap: 8px;
      }
      .tab {
        min-height: 44px;
        font-size: 13px;
        padding-inline: 6px;
      }
      .profile-grid {
        grid-template-columns: 1fr;
      }
      .profile-button {
        width: 46px;
        height: 46px;
      }
    }
  </style>
</head>
<body>
  <div class="locked-view" id="lockedView">
    Ты здесь слишком рано. Ты еще не готов. Оракул ожидает тебя в чате
  </div>
  <div class="entry-view" id="entryView">
    <div class="entry-shell">
      <div class="entry-image-wrap">
        <img
          class="entry-image loading-image"
          id="entryImage"
          src="/static/shop/items/custom-battle-topic.png"
          alt="ETHOS"
        />
      </div>
      <h1 class="entry-title">ETHOS</h1>
      <div class="entry-price" id="entryPrice">...</div>
      <div class="entry-actions">
        <button class="buy" id="entryButton" type="button">Войти в систему</button>
        <a class="buy entry-link" id="entryJoinLink" href="#" target="_blank" rel="noreferrer">
          Перейти в закрытый чат
        </a>
      </div>
      <div class="entry-status" id="entryStatus"></div>
    </div>
  </div>
  <main>
    <header>
      <div class="hero">
        <h1>Магазин</h1>
        <p class="subline">
          Коллекционные предметы, подписки и мудрость оракула
          (персональные рекомендации)
        </p>
      </div>
      <button class="balance" id="balanceButton" type="button">
        <span class="balance-label">Баланс</span>
        <strong class="balance-value" id="balance">...</strong>
      </button>
      <button class="profile-button" id="profileButton" aria-label="Профиль">
        <svg class="profile-glyph" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="8" r="3.5"></circle>
          <path d="M5.5 18.5c1.6-3 4-4.5 6.5-4.5s4.9 1.5 6.5 4.5"></path>
        </svg>
      </button>
    </header>

    <nav class="tabs" aria-label="Разделы магазина">
      <button class="tab" data-tab="shop">Магазин</button>
      <button class="tab active" data-tab="wisdom">Мудрость</button>
      <button class="tab" data-tab="premium">Подписки</button>
    </nav>

    <div class="notice" id="notice"></div>

    <section class="panel" id="shopPanel">
      <div class="grid" id="items"></div>
    </section>

    <section class="panel active" id="wisdomPanel">
      <div class="wisdom-stage">
        <div class="card wisdom-shell">
          <div class="sphere-wrap">
            <img class="sphere-image" id="wisdomImage" src="" alt="Сфера Мудрости" />
          </div>
          <div class="wisdom-copy">
            <h2 id="wisdomTitle">Сфера Мудрости</h2>
            <p class="profile-copy" id="wisdomDescription"></p>
          </div>
          <div class="item-meta">
            <div id="wisdomPrice"></div>
            <button class="buy wisdom-buy" id="wisdomBuyButton">Узнать о себе</button>
          </div>
        </div>
      </div>
    </section>

    <section class="panel" id="premiumPanel">
      <div class="premium-stage" id="premiumBox"></div>
    </section>

    <section class="panel" id="balancePanel">
      <div class="wallet-stage">
        <div class="card wallet-shell">
          <div class="wallet-coin-wrap">
            <img class="wallet-coin loading-image" id="walletCoinImage" src="" alt="PsyCoin" />
          </div>
          <div class="wallet-amount">
            <strong id="walletAmount">...</strong>
            <span class="balance-label">PsyCoin</span>
          </div>
          <div class="wallet-actions">
            <button class="buy icon-buy" id="topUpStarsButton" type="button" aria-label="Купить PsyCoin за звезды">+</button>
            <button class="buy" id="withdrawStarsButton" type="button">⭐ Вывести в звезды</button>
          </div>
          <div class="dev-card" id="balanceDevCard"></div>
        </div>
      </div>
    </section>

    <section class="panel" id="profilePanel">
      <div class="profile-stage">
        <div class="card profile-card">
          <div class="profile-status" id="profileStatus">...</div>
          <div class="profile-grid">
            <div class="profile-metric">
              <span>Индекс субъектности</span>
              <strong id="profileScore">...</strong>
            </div>
            <div class="profile-metric">
              <span>Баланс</span>
              <strong id="profileBalance">...</strong>
            </div>
          </div>
          <div class="profile-collectibles" id="profileCollectibles">
            <div class="profile-collectibles-title">Инвентарь</div>
            <div class="profile-collectibles-list" id="profileCollectiblesList"></div>
          </div>
          <p class="profile-copy" id="profileSummary"></p>
        </div>
      </div>
    </section>
  </main>

  <div class="purchase-overlay" id="purchaseOverlay">
    <div class="card purchase-modal">
      <h2 id="purchaseTitle">Поздравляем с покупкой</h2>
      <p id="purchaseText">Предмет уже находится в вашем профиле.</p>
      <div class="purchase-actions">
        <button class="buy" id="purchaseProfileButton" type="button">Открыть профиль</button>
        <button class="tab active" id="purchaseCloseButton" type="button">Закрыть</button>
      </div>
    </div>
  </div>

  <script>
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();

    const qs = new URLSearchParams(location.search);
    const telegramId = String(
      qs.get('telegram_id') || tg?.initDataUnsafe?.user?.id || ''
    ).trim();

    const balanceButton = document.getElementById('balanceButton');
    const balance = document.getElementById('balance');
    const lockedView = document.getElementById('lockedView');
    const entryView = document.getElementById('entryView');
    const entryImage = document.getElementById('entryImage');
    const entryPrice = document.getElementById('entryPrice');
    const entryButton = document.getElementById('entryButton');
    const entryJoinLink = document.getElementById('entryJoinLink');
    const entryStatus = document.getElementById('entryStatus');
    const profileStatus = document.getElementById('profileStatus');
    const profileScore = document.getElementById('profileScore');
    const profileBalance = document.getElementById('profileBalance');
    const profileSummary = document.getElementById('profileSummary');
    const profileCollectibles = document.getElementById('profileCollectibles');
    const profileCollectiblesList = document.getElementById('profileCollectiblesList');
    const profileButton = document.getElementById('profileButton');
    const itemsBox = document.getElementById('items');
    const premiumBox = document.getElementById('premiumBox');
    const notice = document.getElementById('notice');
    const wisdomImage = document.getElementById('wisdomImage');
    const wisdomTitle = document.getElementById('wisdomTitle');
    const wisdomDescription = document.getElementById('wisdomDescription');
    const wisdomPrice = document.getElementById('wisdomPrice');
    const wisdomBuyButton = document.getElementById('wisdomBuyButton');
    const walletCoinImage = document.getElementById('walletCoinImage');
    const walletAmount = document.getElementById('walletAmount');
    const withdrawStarsButton = document.getElementById('withdrawStarsButton');
    const topUpStarsButton = document.getElementById('topUpStarsButton');
    const balanceDevCard = document.getElementById('balanceDevCard');
    const purchaseOverlay = document.getElementById('purchaseOverlay');
    const purchaseTitle = document.getElementById('purchaseTitle');
    const purchaseText = document.getElementById('purchaseText');
    const purchaseProfileButton = document.getElementById('purchaseProfileButton');
    const purchaseCloseButton = document.getElementById('purchaseCloseButton');
    let currentState = null;

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
      if (type.startsWith('privilege_')) return ['privilege', 'Подписка'];
      return ['collectible', 'Коллекция'];
    }

    function isInventoryType(type) {
      return type === 'collectible' || type.startsWith('privilege_');
    }

    function coinMarkup(iconUrl, amount, className = 'price') {
      return `
        <span class="${className}">
          <img class="coin-icon loading-image" src="${escapeHTML(iconUrl)}" alt="PsyCoin" loading="eager" decoding="async" />
          <span class="coin-amount">${escapeHTML(amount)}</span>
        </span>
      `;
    }

    function renderBalance(iconUrl, amount, vip = null) {
      const vipMarkup = vip ? `
        <span class="vip-badge" aria-label="VIP">
          <img class="vip-icon loading-image" src="${escapeHTML(vip.image_url)}" alt="VIP" loading="eager" decoding="async" />
          <span>VIP</span>
        </span>
      ` : '';
      return `
        <span class="balance-value">
          <span class="coin-amount">${escapeHTML(amount)}</span>
          <img class="coin-icon loading-image" src="${escapeHTML(iconUrl)}" alt="PsyCoin" loading="eager" decoding="async" />
          ${vipMarkup}
        </span>
      `;
    }

    function revealImage(img) {
      img.classList.remove('loading-image');
      img.classList.add('image-ready');
    }

    function hydrateImages(scope = document) {
      scope.querySelectorAll('img').forEach(img => {
        if (img.dataset.hydrated === 'true') return;
        img.dataset.hydrated = 'true';

        const done = () => revealImage(img);
        img.addEventListener('load', done, { once: true });
        img.addEventListener('error', done, { once: true });

        if (img.complete && img.naturalWidth > 0) {
          revealImage(img);
        }
      });
    }

    function openPanel(panelId) {
      document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));
      document.getElementById(panelId).classList.add('active');
    }

    function showLocked() {
      document.body.classList.add('locked');
      document.body.classList.remove('entry');
      lockedView.textContent = 'Ты здесь слишком рано. Ты еще не готов. Оракул ожидает тебя в чате';
    }

    function showEntry(data) {
      currentState = data;
      document.body.classList.add('entry');
      document.body.classList.remove('locked');
      entryPrice.textContent = `Вход: ${data.system_entry_star_price} ⭐`;
      entryButton.textContent = `Войти за ${data.system_entry_star_price} ⭐`;
      entryJoinLink.href = data.closed_group_invite_url || '#';
      entryJoinLink.classList.remove('visible');
      entryStatus.textContent = 'Проверка пройдена. Остался вход в закрытый контур.';
      hydrateImages(entryView);
    }

    function showBalanceCard(html) {
      balanceDevCard.classList.add('visible');
      balanceDevCard.innerHTML = html;
    }

    function showPurchaseOverlay(title, text) {
      purchaseTitle.textContent = title;
      purchaseText.textContent = text;
      purchaseOverlay.classList.add('visible');
    }

    function hidePurchaseOverlay() {
      purchaseOverlay.classList.remove('visible');
    }

    async function fetchState() {
      const res = await fetch(
        `/api/v1/marketplace/state?telegram_id=${encodeURIComponent(telegramId)}`
      );
      if (res.status === 403) {
        showLocked();
        return null;
      }
      if (!res.ok) {
        notice.textContent = 'Пользователь не найден. Сначала напишите боту /start.';
        return null;
      }
      return await res.json();
    }

    function openInvoice(invoiceUrl, onPaid) {
      if (!invoiceUrl) {
        throw new Error('invoice_url is empty');
      }
      if (tg?.openInvoice) {
        tg.openInvoice(invoiceUrl, status => {
          if (status === 'paid') onPaid?.();
          if (status === 'failed') notice.textContent = 'Оплата не прошла. Попробуйте еще раз.';
        });
        return;
      }
      window.open(invoiceUrl, '_blank', 'noopener,noreferrer');
      notice.textContent = 'Счет открыт в новом окне. После оплаты обновите магазин.';
    }

    async function waitForFollower() {
      entryStatus.textContent = 'Оплата принята. Подтверждаю вход...';
      for (let attempt = 0; attempt < 12; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const data = await fetchState();
        if (data?.lifecycle_status === 'follower') {
          currentState = data;
          entryStatus.textContent = 'Вход подтвержден. Закрытый чат открыт.';
          entryJoinLink.href = data.closed_group_invite_url;
          entryJoinLink.classList.add('visible');
          if (data.closed_group_invite_url && tg?.openTelegramLink) {
            tg.openTelegramLink(data.closed_group_invite_url);
          }
          return;
        }
      }
      entryStatus.textContent = 'Оплата прошла. Если кнопка чата не появилась, закройте и снова откройте ETHOS через синюю кнопку.';
    }

    async function startSystemEntryPayment() {
      if (!telegramId) return;
      entryStatus.textContent = 'Готовлю счет Telegram Stars...';
      entryButton.disabled = true;
      try {
        const res = await fetch('/api/v1/marketplace/stars/system-entry', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            telegram_id: Number(telegramId),
            star_amount: currentState?.system_entry_star_price || 50
          })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          entryStatus.textContent = data.message || data.detail || 'Не удалось создать счет.';
          return;
        }
        if (!data.invoice_url) {
          entryStatus.textContent = data.message || 'Вход уже открыт.';
          await load();
          return;
        }
        entryStatus.textContent = data.message;
        openInvoice(data.invoice_url, waitForFollower);
      } catch (error) {
        entryStatus.textContent = 'Не удалось открыть оплату. Проверьте связь и попробуйте еще раз.';
      } finally {
        entryButton.disabled = false;
      }
    }

    async function refreshAfterPayment() {
      for (let attempt = 0; attempt < 10; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 900));
        const data = await fetchState();
        if (data && data.token_balance !== currentState?.token_balance) {
          await load();
          notice.textContent = 'PsyCoin зачислены.';
          return;
        }
      }
      await load();
    }

    async function buyStarsTopUp(starAmount) {
      notice.textContent = '';
      showBalanceCard('Готовлю счет Telegram Stars...');
      try {
        const res = await fetch('/api/v1/marketplace/stars/topup', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            telegram_id: Number(telegramId),
            star_amount: starAmount
          })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          showBalanceCard(escapeHTML(data.message || data.detail || 'Не удалось создать счет.'));
          return;
        }
        showBalanceCard(escapeHTML(data.message));
        openInvoice(data.invoice_url, refreshAfterPayment);
      } catch (error) {
        showBalanceCard('Не удалось открыть счет. Проверьте связь и попробуйте еще раз.');
      }
    }

    function renderTopUpCard() {
      const rate = currentState?.psycoin_per_star || 5;
      const packages = [50, 100, 200, 500];
      showBalanceCard(`
        <div style="display:grid;gap:12px;text-align:left">
          <strong>Обмен Stars на PsyCoin</strong>
          <span>Курс: 1 ⭐ = ${escapeHTML(rate)} PsyCoin</span>
          <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px">
            ${packages.map(stars => `
              <button class="buy" type="button" data-stars="${stars}">
                ${stars} ⭐ → ${stars * rate} PsyCoin
              </button>
            `).join('')}
          </div>
        </div>
      `);
      balanceDevCard.querySelectorAll('[data-stars]').forEach(button => {
        button.addEventListener('click', () => buyStarsTopUp(Number(button.dataset.stars)));
      });
    }

    async function submitWithdrawal() {
      const tokenAmount = currentState?.psycoin_withdraw_min || 1000;
      showBalanceCard('Отправляю заявку администратору...');
      try {
        const res = await fetch('/api/v1/marketplace/stars/withdraw', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            telegram_id: Number(telegramId),
            token_amount: tokenAmount
          })
        });
        const data = await res.json();
        const message = data.message || data.detail || 'Заявка обработана.';
        await load();
        openPanel('balancePanel');
        showBalanceCard(escapeHTML(message));
      } catch (error) {
        showBalanceCard('Не удалось отправить заявку. Проверьте связь и попробуйте еще раз.');
      }
    }

    function renderWithdrawCard() {
      const min = currentState?.psycoin_withdraw_min || 1000;
      const rate = currentState?.psycoin_per_star || 5;
      const stars = Math.floor(min / rate);
      const enough = (currentState?.token_balance || 0) >= min;
      showBalanceCard(`
        <div style="display:grid;gap:12px;text-align:left">
          <strong>Вывод PsyCoin в Stars</strong>
          <span>Минимум: ${escapeHTML(min)} PsyCoin = ${escapeHTML(stars)} ⭐</span>
          <span>Заявка уйдет администратору. PsyCoin будут списаны и зарезервированы под ручную выплату.</span>
          <button class="buy" type="button" id="submitWithdrawalButton" ${enough ? '' : 'disabled'}>
            ${enough ? 'Подать заявку' : 'Недостаточно PsyCoin'}
          </button>
        </div>
      `);
      const button = document.getElementById('submitWithdrawalButton');
      button?.addEventListener('click', submitWithdrawal);
    }

    async function load() {
      if (!telegramId) {
        notice.textContent = 'Откройте магазин из Telegram или передайте telegram_id в ссылке.';
        return;
      }

      notice.textContent = '';
      document.body.classList.remove('locked');
      document.body.classList.remove('entry');
      const data = await fetchState();
      if (!data) return;
      currentState = data;
      if (data.lifecycle_status === 'beginner') {
        showEntry(data);
        return;
      }
      const collectibles = data.items.filter(item => item.item_type === 'collectible');
      const wisdom = data.items.find(item => item.item_type === 'wisdom_sphere');
      const premium = data.items.find(item => item.item_type.startsWith('privilege_'));
      const ownedInventory = data.inventory || [];
      const ownedPremium = data.purchases.find(
        item => item.item_type === 'privilege_custom_battle_topic'
      );
      const premiumBadge = ownedPremium || null;

      balance.innerHTML = renderBalance(data.currency_icon_url, data.token_balance, premiumBadge);
      walletCoinImage.src = data.currency_icon_url;
      walletCoinImage.classList.add('loading-image');
      walletCoinImage.classList.remove('image-ready');
      walletAmount.textContent = data.token_balance;
      balanceDevCard.classList.remove('visible');
      balanceDevCard.innerHTML = '';
      profileStatus.textContent = statusLabels[data.status] || data.status;
      profileScore.textContent = `${data.subjectivity_score}/100`;
      profileBalance.innerHTML = coinMarkup(
        data.currency_icon_url,
        data.token_balance,
        'price profile-balance-value'
      );
      profileSummary.textContent = data.profile_summary ||
        'Психологический портрет еще формируется.';
      if (ownedInventory.length) {
        profileCollectibles.classList.add('visible');
        profileCollectiblesList.innerHTML = ownedInventory.map(item => `
          <div class="inventory-tile">
            <img
              class="profile-collectible loading-image"
              src="${escapeHTML(item.image_url)}"
              alt="${escapeHTML(item.title)}"
              title="${escapeHTML(item.title)}"
              loading="lazy"
              decoding="async"
            />
            <span>${escapeHTML(item.title)}</span>
          </div>
        `).join('');
      } else {
        profileCollectibles.classList.remove('visible');
        profileCollectiblesList.innerHTML = '';
      }

      itemsBox.innerHTML = collectibles.map(item => {
        const [kind, label] = typeLabel(item.item_type);
        const disabled = !item.can_purchase || data.token_balance < item.price_tokens ? 'disabled' : '';
        const buttonLabel = item.is_owned ? 'Уже в профиле' : 'Купить';
        const ownedBadge = item.is_owned ? '<span class="badge owned">Уже ваш</span>' : '';
        return `
          <article class="card item">
            <div class="item-head">
              <img
                class="item-media loading-image"
                src="${escapeHTML(item.image_url)}"
                alt="${escapeHTML(item.title)}"
                loading="lazy"
                decoding="async"
              />
              <div class="item-copy">
                <div class="item-top">
                  <h2>${escapeHTML(item.title)}</h2>
                  <div>
                    <span class="badge ${kind}">${label}</span>
                    ${ownedBadge}
                  </div>
                </div>
                <p>${escapeHTML(item.description)}</p>
              </div>
            </div>
            <div class="item-meta">
              ${coinMarkup(item.currency_icon_url, item.price_tokens)}
              <button class="buy" ${disabled} onclick="buyById('${item.id}')">${buttonLabel}</button>
            </div>
          </article>
        `;
      }).join('');

      if (wisdom) {
        wisdomImage.src = wisdom.image_url;
        wisdomImage.classList.add('loading-image');
        wisdomImage.classList.remove('image-ready');
        wisdomTitle.textContent = wisdom.title;
        wisdomDescription.textContent = wisdom.description;
        wisdomPrice.innerHTML = coinMarkup(wisdom.currency_icon_url, wisdom.price_tokens);
        wisdomBuyButton.disabled = !wisdom.can_purchase || data.token_balance < wisdom.price_tokens;
        wisdomBuyButton.onclick = () => buyById(wisdom.id);
      }

      premiumBox.innerHTML = premium ? `
        <article class="card premium-card">
          <div class="premium-head">
            <div class="item-copy">
              <div class="item-top">
                <h2>${escapeHTML(premium.title)}</h2>
                <div>
                  <span class="badge privilege">Подписка</span>
                  ${premium.is_owned ? '<span class="badge owned">Активно</span>' : ''}
                </div>
              </div>
              <p class="premium-copy">${escapeHTML(premium.description)}</p>
            </div>
            <img
              class="item-media premium-media loading-image"
              src="${escapeHTML(premium.image_url)}"
              alt="${escapeHTML(premium.title)}"
              loading="lazy"
              decoding="async"
            />
          </div>
          <div class="item-meta">
            ${coinMarkup(premium.currency_icon_url, premium.price_tokens)}
            <button
              class="buy"
              ${!premium.can_purchase || data.token_balance < premium.price_tokens ? 'disabled' : ''}
              onclick="buyById('${premium.id}')"
            >${premium.is_owned ? 'Уже активно' : 'Купить'}</button>
          </div>
        </article>
      ` : '<div class="empty">Премиум пока недоступен.</div>';

      hydrateImages(document);
    }

    async function buyById(itemId) {
      notice.textContent = 'Оформляю покупку...';
      const res = await fetch('/api/v1/marketplace/buy', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          telegram_id: Number(telegramId),
          item_id: itemId
        })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        notice.textContent = data.message || 'Покупка не выполнена.';
        return;
      }
      notice.textContent = data.message || 'Готово.';
      await load();
      if (isInventoryType(data.purchase_item_type || '')) {
        showPurchaseOverlay(
          'Поздравляем с покупкой',
          `${data.purchase_title || 'Предмет'} уже находится в вашем профиле, во вкладке Инвентарь.`
        );
      }
    }

    document.querySelectorAll('.tab').forEach(button => {
      button.addEventListener('click', () => {
        document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));
        document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
        button.classList.add('active');
        document.getElementById(button.dataset.tab + 'Panel').classList.add('active');
      });
    });

    balanceButton.addEventListener('click', () => {
      openPanel('balancePanel');
    });

    profileButton.addEventListener('click', () => {
      openPanel('profilePanel');
    });

    entryButton.addEventListener('click', startSystemEntryPayment);
    withdrawStarsButton.addEventListener('click', renderWithdrawCard);
    topUpStarsButton.addEventListener('click', renderTopUpCard);
    purchaseProfileButton.addEventListener('click', () => {
      hidePurchaseOverlay();
      openPanel('profilePanel');
    });
    purchaseCloseButton.addEventListener('click', hidePurchaseOverlay);
    purchaseOverlay.addEventListener('click', event => {
      if (event.target === purchaseOverlay) hidePurchaseOverlay();
    });

    load();
  </script>
</body>
</html>"""
