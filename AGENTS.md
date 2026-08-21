# 🌾 Ферма — AGENTS.md

## Проект

VK Mini App — однопользовательская мотивационная игра-вышивка в сеттинге
волшебной фермы. Игрок реально вышивает → фоткает результат → получает
«крестики» → тратит их на выращивание растений, производства и выполнение
заказов от магов и русалок → зарабатывает монеты и продвигается по раундам.

Цифровой спутник физической настольной игры (конверты/наклейки/скретч-карты),
адаптированный под сольный формат.

Полные правила — `docs/Правила.md`. План реализации — `docs/PLAN.md`.

## Важное

- Если пользователь задает вопрос — сперва ответить.
- **Не додумывать за пользователем** - сначала уточни.
- **Если что-то не понятно — задать вопрос пользователю прежде чем делать.** Не додумывать.
- **Сначала пояснение, потом код.** Перед любым изменением кода — объяснить, что именно будет сделано и почему. Дождаться утверждения пользователем. Только после утверждения писать код.
- **⛔ Тесты на каждое изменение Python-кода.** См. раздел «Обязательно: тесты». Задача не завершена, пока тесты не зелёные.

## Стек

| Компонент | Технология |
|-----------|-----------|
| Backend API | Python 3.14 / FastAPI / SQLAlchemy 2.x / Alembic |
| Database | SQLite (WAL mode, foreign_keys=ON) |
| Frontend | React 18 / TypeScript / Vite 7 |
| Auth | Проверка подписи VK (`sign`) + JWT (python-jose) |
| Production server | gunicorn + uvicorn.workers.UvicornWorker |
| Process manager | systemd |
| Python venv | `api/venv/Scripts/python.exe` (Windows) / `api/venv/bin/python` (Linux) |

Конвенции бэкенда/миграций/деплоя перенесены 1:1 из проекта
«Затерянный мир» (`D:\Боты\Затерянный мир`), который в свою очередь перенёс их
из «Коллекция драконов».

## Структура

```
/ Ферма/
  api/                      # Python backend (FastAPI + Alembic)
    main.py                 # FastAPI app: init_db + lifespan + CORS + routers + health
    models.py               # Все ORM модели
    db.py                   # Engine + PRAGMA + SessionLocal + init_db/get_db
    config.py               # env-конфиг (load_dotenv + _env_int)
    deps.py                 # get_db, get_current_user (JWT), require_role
    middleware.py           # Логирование ошибочных запросов (4xx/5xx)
    alembic/
      env.py                # batch mode + URL override из config
      alembic.ini           # sqlalchemy.url = sqlite:///farm.db
      script.py.mako        # шаблон миграций
      versions/             # <rev>_<slug>.py — миграции
    routes/
      auth.py               # /api/auth/session (проверка подписи VK) + JWT
      me.py                 # /api/me — профиль, крестики, монеты, раунд
      stitches.py           # /api/stitches/reports — фото-отчёты вышивки
      plants.py             # /api/plants — каталог растений
      farm.py               # /api/farm — обзор, грядки, производства, крафт, инвентарь
      orders.py             # /api/orders — NPC-заказы
      settings.py           # /api/settings — нормы, курсы, авто-зачёт
    services/
      vk_sign.py            # проверка подписи VK (AES-схема)
      auth.py               # JWT-выпуск
      uploads.py            # сохранение/удаление фото (Pillow-пережатие)
  frontend/                 # React SPA
    src/
      context/VkBridgeContext.tsx   # VK Bridge (vkUserId, демо-режим)
      context/SessionContext.tsx    # токен + /me
      api/client.ts                # axios, Bearer-интерцептор
      api/endpoints.ts             # все вызовы
      api/media.ts                 # URL-хелпер для фото
      auth/adminGate.ts             # заглушка: доступ только админам (VK-ID whitelist)
      components/
        MiniAppShell.tsx           # гамбургер-навигация
        Background.tsx             # фон страницы (CSS-переменная)
      pages/
        Farm.tsx                   # главная: статы, грядки, производства, склад
        Orders.tsx                 # NPC-заказы
        Profile.tsx                # статистика + дневник вышивки
        Admin.tsx                  # модерация фото + настройки (только admin)
  deploy/                   # bash-скрипты + systemd units
    deploy.sh               # полнооткатный деплой (trap on_error → rollback_all)
    backup.sh               # ежедневний бэкап БД
    magicfarm-api.service   # systemd: gunicorn на 127.0.0.1:8003
    magicfarm-bot.service   # заготовка (TODO: когда бот появится)
    nginx-magicfarm.conf    # location /magicfarm/ для FastPanel2 (belovolovhome.ru)
  dev.ps1                   # локальный запуск (Windows): venv + alembic + uvicorn + фронт
  docs/
    Правила.md              # структурированные правила игры (из pptx)
    PLAN.md                 # план реализации (источник истины)
```

## База данных — ключевые таблицы

- **users** — `vk_id` PK, `role` (admin/player), `crosses_balance` (расходный), `crosses_total` (стат), `coins`, `round`
- **settings** — key-value (нормы, курсы, флаги)
- **stitch_reports** — фото-отчёты вышивки (`status`: pending/accepted/rejected)
- **plants** — каталог растений (code, name, category, level, norm_per_crystal, бонусы)
- **plots** — грядки игрока (`status`: planted/grown; `accumulated`/`required` крестиков)
- **productions** — установленные производства (alchemy/sewing/workshop)
- **products** — каталог товаров (звёздочки, привязка к production_kind)
- **inventory** — склад готовых товаров игрока
- **orders** — NPC-заказы (`status`: open/fulfilled/cancelled)
- **request_logs** — для middleware

Полная схема — в `api/models.py` и миграции `api/alembic/versions/0001_initial.py`.

## Роли и права

- **admin** — модерация фото-отчётов (в режиме review), управление настройками.
- **player** — всё геймплейное: вышивка, грядки, производства, заказы.

Роль `admin` назначается по `ADMIN_VK_IDS` при логине (см. `routes/auth.py`).

## Ключевая механика — крестики

- **Фото-вышивка** (`POST /api/stitches/reports`): игрок грузит фото + число
  крестиков. При `auto_credit=on` (по умолчанию) — мгновенный зачёт:
  `crosses_balance += amount` И `crosses_total += amount`. Иначе ждёт модерации admin'ом.
- **Расход крестиков** — на выращивание грядок (`invest`) и крафт товаров (`craft`).
- **Нормы** — по кристаллам (🟢🔵🟣), вариант таблицы задаётся настройкой
  `crystal_rate_variant` (1–8). Считается через `routes/settings.crystal_norm()`.

## Как запустить

```powershell
.\dev.ps1                       # Всё сразу (backend :8003 + frontend :5175)
```

(Флаги `-NoFrontend` / `-NoBackend`.)

## Как запустить тесты

```powershell
# Python (API) — из папки api/
cd api
.\venv\Scripts\python.exe -m pytest tests/ -v --tb=short

# Frontend — пока нет тестов (vitest добавляется при нетривиальной логике)
```

Тесты используют in-memory SQLite (`conftest.py`) — чистая БД на каждый запуск,
на прод-БД не влияют. Фикстуры-клиенты: `client` (401), `admin_client`,
`player_client`; `make_user_client(vk_id, role)` для многоигровых тестов.

## Миграции

```powershell
cd api
.\venv\Scripts\python.exe -m alembic upgrade head
```

`alembic.ini` в `api/`, `env.py` переопределяет URL из `config.DATABASE_URL`.
Миграции **НЕ применяются при runtime** — `init_db()` делает `create_all`
для безопасности, реальные изменения схемы через `alembic upgrade head`.

### ⛔ Обязательно: миграция после ЛЮБОГО изменения models.py

**Правило:** если ты изменил(а) `api/models.py` (добавил/удалил колонку,
новую таблицу, изменил тип колонки, переименовал) — ОБЯЗАТЕЛЬНО:

1. **Создать миграцию:**
   ```powershell
   cd api
   .\venv\Scripts\python.exe -m alembic revision --autogenerate -m "краткое_описание"
   ```
2. **Проверить** содержимое сгенерированного файла в `api/alembic/versions/` — autogenerate иногда добавляет лишние изменения (NOT NULL, type changes), их можно оставить, если они корректны.
3. **Применить миграцию:**
   ```powershell
   cd api
   .\venv\Scripts\python.exe -m alembic upgrade head
   ```
4. **Убедиться, что dev.ps1 тоже применит миграцию** (на старте dev.ps1 делает `alembic upgrade head` автоматически — нужно просто перезапустить сервер).

Без миграции прод-БД и dev-БД не будут соответствовать моделям → 500 ошибки «no such column» или «no such table».

## ⛔ Обязательно: тесты на каждое изменение (НЕПРЕЛОЖНОЕ ПРАВИЛО)

Это правило нарушать нельзя — ни в одной задаче. Тесты — это часть определения
сделанного, а не отдельный шаг «на потом».

**Правило:** после ЛЮБОГО изменения Python-кода — ОБЯЗАТЕЛЬНО:

1. **Написать тесты** на новое поведение: happy path, ошибки (4xx), права.
2. **Запустить полный набор:**
   ```powershell
   cd api
   .\venv\Scripts\python.exe -m pytest tests/ -v --tb=short
   ```
3. **Добиться зелёного.**
4. **Не удалять старые тесты** ради прохождения новых — признак регрессии.

**Паттерны тестов** (см. `api/tests/conftest.py`):
- In-memory SQLite + `StaticPool`, env до импорта config/db.
- Авторизация через фикстуры-клиенты, НЕ через ручную подстановку токенов.
- Сиды растений/товаров/настроек — в `conftest.py` (`seed_farm`).

## Деплой

Полнооткатный скрипт `deploy/deploy.sh` (структурно идентичен lostworld/dragons):

1. Фиксация `PREV_REV` (Alembic) + `PREV_GIT`.
2. tar-бэкап + бэкап БД + бэкап dist.
3. `git fetch` + `reset --hard`.
4. `pip install` + `alembic upgrade head`.
5. `npm install` + `npm run build`.
6. `systemctl restart magicfarm-api`.
7. Health-check (5 попыток).

При ошибке — `trap on_error` → `rollback_all`. Режим `-recovery` —
интерактивное восстановление из tar-архива.

Константы: `APP_DIR=/opt/magicfarm`, `DB_FILE=/opt/magicfarm/api/farm.db`.
Бэкапы: `$API_DIR/backups` (10 копий), `/opt/magicfarm-backups` (5 архивов).

## Конвенции кода

- Python: никаких комментариев без запроса.
- TypeScript: без комментариев, без лишних типов.
- SQLAlchemy: `Column`, `Integer`, `String`, `Boolean`, `Text`, `ForeignKey`, `default=`.
- Все импорты моделей внутри функций (lazy import) в `services/*.py`.
- Пустые строки между определениями классов/функций.
- Имена миграций: `<rev>_<slug>.py`.
- **Если что-то не понятно — задать вопрос пользователю прежде чем делать.**
- **Авто-код:** поле `code` генерируется автоматически из названия (рус→лат транслитерация + `_auto_code` в `admin_catalog.py`). В формах админки поле «Код» **отсутствует**. В тестах — проверять что code не пустой, а не конкретное значение.

## ⚠️ Кодировки файлов (НЕПРЕЛОЖНОЕ ПРАВИЛО)

**Все исходники проекта — UTF-8 без BOM, переводы строк LF.** Кириллица в
`frontend/src/*.tsx`, `api/*.py`, `docs/*.md` и т.д. обязана оставаться UTF-8.

**ЗАПРЕЩЕНО использовать PowerShell-командлеты для чтения/записи файлов проекта:**
`Get-Content`, `Set-Content`, `Out-File`, `Add-Content`, `>` и т.п.
PowerShell 5.1 без явного `-Encoding` читает файл без BOM как Windows-1251
(системная локаль) и пишет обратно в другой кодировке → **вся кириллица в файле
превращается в «кракозябры»** (`в”Ђ` / `Р РµС†` и т.п.), а LF → CRLF.
Именно так однажды была сломана кодировка `frontend/src/pages/Admin.tsx`.

**Можно и нужно:**
- Читать/редактировать файлы только штатными инструментами (Read/Write/Edit) —
  они сохраняют UTF-8.
- Если обойтись без шелла нельзя — использовать Python с явной кодировкой:
  ```powershell
  api\venv\Scripts\python.exe -c "data=open('frontend/src/pages/Admin.tsx',encoding='utf-8').read(); ..."
  ```
  (запись всегда `open(path, 'w', encoding='utf-8', newline='\n')`).
- Обрезка/удаление хвоста файла через `Get-Content | Set-Content` — **запрещено**.
  Только инструмент Edit или Python.

**Проверка после любых файловых операций из шелла:** открыть файл и убедиться,
что русский текст читается нормально (а не `в”Ђ`/`Р РµС†`), и что `git diff`
показывает только ожидаемые изменения (не «весь файл переписан»).

## 🔍 Graphify — граф знаний проекта

This project has a graphify knowledge graph at graphify-out/.

### Rules:

- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run graphify update . to keep the graph current (AST-only, no API cost)

При **любом поиске по коду** — сначала использовать graphify, а не grep/glob:

```powershell
cd api
.\venv\Scripts\python.exe -m graphify query "<вопрос>"
```

Граф построен для всего проекта (`graphify-out/graph.json`) и покрывает:
- API-роуты, модели, сервисы, тесты
- Фронтенд: страницы, компоненты, контексты, API-клиент

**После создания/удаления файлов** — обновить граф:

```powershell
cd api
.\venv\Scripts\python.exe -m graphify --update D:/Боты/Ферма
```
