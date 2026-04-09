# Project Guidelines

## Overview

Telegram bot (aiogram 3.x, Python 3.12+) that helps users quit smoking using the Tabex (cytisine) medication protocol. The bot manages the full 25-day treatment course: onboarding, dose scheduling, push notifications, progress tracking, and quit-day enforcement.

## Architecture

```
bot/
├── __main__.py          # Entry point, bot runner
├── config.py            # Settings via pydantic-settings (env vars)
├── handlers/            # aiogram routers (start, schedule, progress, settings)
├── middlewares/          # DB session, i18n, throttling
├── keyboards/           # Inline and reply keyboard builders
├── services/            # Business logic (schedule calculator, notification planner)
├── models/              # SQLAlchemy ORM models (User, Course, DoseLog)
├── db/                  # Engine, session factory, migrations (alembic)
├── taskiq_broker.py     # TaskIQ broker, schedule source, scheduler
├── tasks.py             # TaskIQ tasks (dose reminders, daily scheduler)
└── utils/               # Helpers, date math, text templates
```

## Tabex Protocol (25 days)

This is the core domain — all scheduling logic must follow this exactly:

| Period  | Days  | Interval   | Tablets/day |
| ------- | ----- | ---------- | ----------- |
| Phase 1 | 1–3   | every 2h   | 6           |
| Phase 2 | 4–12  | every 2.5h | 5           |
| Phase 3 | 13–16 | every 3h   | 4           |
| Phase 4 | 17–20 | every 5h   | 3           |
| Phase 5 | 21–25 | every 5h   | 1–2         |

- **Day 5**: user MUST stop smoking completely
- Tablets are taken only during waking hours (user configures wake/sleep times)
- Missed doses should be logged but NOT doubled

## Tech Stack

- **Bot framework**: aiogram 3.x with `Router`-based handler organization
- **Database**: PostgreSQL + SQLAlchemy 2.x (async), Alembic for migrations
- **Scheduler**: TaskIQ + taskiq-redis (ListQueueBroker, ListRedisScheduleSource) for async task queue and scheduling
- **Settings**: pydantic-settings, all config via environment variables
- **Package manager**: uv

## Code Style

- Language in code: English (variable names, comments, docstrings)
- Language for user-facing messages: Russian
- Type hints on all public functions
- Async everywhere — no sync DB calls or blocking I/O
- Handler functions go in `bot/handlers/`, one file per logical group
- Business logic stays in `bot/services/`, never in handlers directly

## Build and Test

```bash
uv sync                          # Install dependencies
uv run alembic upgrade head      # Apply migrations
uv run python -m bot             # Start the bot
uv run taskiq worker bot.taskiq_broker:broker --fs-discover  # Start TaskIQ worker
uv run taskiq scheduler bot.taskiq_broker:scheduler          # Start TaskIQ scheduler
uv run pytest                    # Run tests
uv run pytest --cov=bot          # With coverage

# Docker (recommended)
docker compose up --build        # Start everything
```

## Conventions

- FSM (Finite State Machine) for multi-step conversations (aiogram FSM)
- Callback data classes via `aiogram.filters.callback_data.CallbackData`
- All user-facing strings in `bot/utils/texts.py` (single source for i18n later)
- Timezone-aware datetimes everywhere (`datetime.datetime` with `tzinfo`)
- User timezone stored in DB, all schedule calculations in user's local time
- Env vars prefixed with `BOT_` (e.g., `BOT_TOKEN`, `BOT_DB_URL`)
