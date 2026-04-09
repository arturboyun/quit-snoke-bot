# Quit Smoke Bot 🚭

Telegram-бот для отказа от курения с препаратом **Табекс** (цитизин). Бот ведёт пользователя через полный 25-дневный курс: онбординг, расписание приёма, push-уведомления, отслеживание прогресса и контроль дня отказа.

## Возможности

- 📋 Полная схема приёма Табекс (5 фаз, 25 дней)
- ⏰ Напоминания о каждом приёме таблетки по расписанию
- 🚭 Уведомление на 5-й день — полный отказ от курения
- 📊 Отслеживание прогресса с визуализацией
- ⚙️ Настройка часового пояса и времени сна/подъёма
- 🔄 Автоматическое ежедневное планирование доз

## Протокол Табекс (25 дней)

| Фаза | Дни   | Интервал  | Таблеток/день |
|------|-------|-----------|---------------|
| 1    | 1–3   | 2 часа    | 6             |
| 2    | 4–12  | 2.5 часа  | 5             |
| 3    | 13–16 | 3 часа    | 4             |
| 4    | 17–20 | 5 часов   | 3             |
| 5    | 21–25 | 5 часов   | 1–2           |

> **День 5**: пользователь должен полностью прекратить курить.

## Архитектура

```
bot/
├── __main__.py          # Точка входа, запуск бота
├── config.py            # Настройки через pydantic-settings
├── taskiq_broker.py     # TaskIQ брокер, планировщик
├── tasks.py             # TaskIQ задачи (напоминания, расписание)
├── handlers/            # aiogram роутеры
│   ├── start.py         # /start + онбординг FSM
│   ├── course.py        # /start_course, /cancel_course
│   ├── progress.py      # /progress, /schedule, /help
│   └── settings.py      # /settings
├── services/            # Бизнес-логика
│   ├── schedule.py      # Калькулятор расписания доз
│   └── course.py        # CRUD: пользователи, курсы, логи
├── models/              # SQLAlchemy ORM модели
├── keyboards/           # Inline-клавиатуры
├── middlewares/         # Throttling
├── utils/texts.py       # Все строки интерфейса (русский)
└── db/                  # SQLAlchemy engine, Alembic миграции
```

## Стек

- **Python** 3.12+
- **aiogram** 3.x — Telegram Bot API
- **PostgreSQL** + **SQLAlchemy** 2.x (async) — база данных
- **Alembic** — миграции
- **TaskIQ** + **taskiq-redis** — очередь задач и планирование
- **Redis** — брокер сообщений
- **Docker Compose** — оркестрация

## Быстрый старт

### Docker (рекомендуется)

```bash
cp .env.example .env
# Отредактируй .env — укажи BOT_TOKEN
docker compose up --build
```

### Локально

```bash
# Установка зависимостей
uv sync

# Применение миграций (нужен запущенный PostgreSQL)
uv run alembic upgrade head

# Запуск бота
uv run python -m bot

# Запуск TaskIQ worker (в отдельном терминале)
uv run taskiq worker bot.taskiq_broker:broker --fs-discover

# Запуск TaskIQ scheduler (в отдельном терминале)
uv run taskiq scheduler bot.taskiq_broker:scheduler --skip-first-run
```

## Переменные окружения

| Переменная     | Описание                         | По умолчанию                                          |
|----------------|----------------------------------|-------------------------------------------------------|
| `BOT_TOKEN`    | Токен Telegram бота              | **обязательно**                                       |
| `BOT_DB_URL`   | URL подключения к PostgreSQL     | `postgresql+asyncpg://bot:bot@localhost:5432/quit_smoke` |
| `BOT_REDIS_URL`| URL подключения к Redis          | `redis://localhost:6379/0`                            |

## Команды бота

| Команда          | Описание                          |
|------------------|-----------------------------------|
| `/start`         | Начать / перезапустить бота       |
| `/start_course`  | Начать 25-дневный курс            |
| `/progress`      | Посмотреть прогресс               |
| `/schedule`      | Расписание приёма на сегодня      |
| `/settings`      | Изменить настройки                |
| `/cancel_course` | Отменить текущий курс             |
| `/help`          | Справка по командам               |

## Тестирование

```bash
uv sync --dev
uv run pytest
uv run pytest --cov=bot    # с покрытием
```

## Docker Compose — сервисы

| Сервис      | Назначение                                |
|-------------|-------------------------------------------|
| `postgres`  | База данных PostgreSQL 16                 |
| `redis`     | Брокер для TaskIQ                         |
| `migrate`   | Одноразовое применение миграций           |
| `bot`       | Telegram-бот (polling)                    |
| `worker`    | TaskIQ worker — выполнение задач          |
| `scheduler` | TaskIQ scheduler — планирование задач     |
