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
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <meta http-equiv="Expires" content="0" />
  <title>Магазин</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    /* ... same CSS ... */
  </style>
</head>
<body>
  <!-- ... same HTML ... -->

  <script>
    // ... same JS ...

    function showAdminPanel() {
      document.body.classList.add('locked');
      document.body.classList.remove('entry');
      
      lockedView.innerHTML = `
        <div style="max-width: 460px; margin: 0 auto; text-align: left;">
          <h2 style="margin: 0 0 24px 0; font-size: 24px; text-align: center; color: #ffe9f0;">Админ-панель ETHOS</h2>
          
          <div style="display: grid; gap: 12px;">
            <button onclick="openAdminModal('grant')" class="buy" style="width:100%; padding:16px; font-size:15px; text-align:left;">
              💰 Подарить псикоины
            </button>
            <button onclick="openAdminModal('setscore')" class="buy" style="width:100%; padding:16px; font-size:15px; text-align:left;">
              📊 Установить индекс субъектности
            </button>
            <button onclick="openAdminModal('setstatus')" class="buy" style="width:100%; padding:16px; font-size:15px; text-align:left;">
              🏷️ Назначить уровень пользователя
            </button>
            <button onclick="openAdminModal('setlifecycle')" class="buy" style="width:100%; padding:16px; font-size:15px; text-align:left;">
              🔄 Установить системный статус
            </button>
            <button onclick="openAdminModal('resetuser')" class="buy" style="width:100%; padding:16px; font-size:15px; text-align:left;">
              🔄 Сбросить профиль
            </button>
            <button onclick="openAdminModal('users')" class="buy" style="width:100%; padding:16px; font-size:15px; text-align:left;">
              👥 Показать пользователей
            </button>
          </div>
          
          <p style="margin-top: 28px; font-size: 13px; color: #aaa; text-align: center; line-height: 1.5;">
            Нажми на действие → заполни данные → команда скопируется и отправь её в чат боту
          </p>
        </div>
      `;
    }

    // ... rest of the JS remains the same ...
  </script>
</body>
</html>"""
