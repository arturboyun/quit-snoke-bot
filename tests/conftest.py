import datetime
import os
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set env vars before any bot imports
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("BOT_DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BOT_REDIS_URL", "redis://localhost:6379/0")

from bot.models.base import Base


@pytest.fixture
def wake_time() -> datetime.time:
    return datetime.time(8, 0)


@pytest.fixture
def sleep_time() -> datetime.time:
    return datetime.time(22, 0)


@pytest.fixture
def course_start_date() -> datetime.date:
    return datetime.date(2026, 1, 1)


@pytest.fixture
def timezone() -> str:
    return "Europe/Moscow"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def mock_session_factory(db_engine):
    """Patch session_factory in all modules that import it."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def _factory():
        async with factory() as session:
            yield session

    targets = [
        "bot.db.engine.session_factory",
        "bot.handlers.start.session_factory",
        "bot.handlers.course.session_factory",
        "bot.handlers.settings.session_factory",
        "bot.handlers.menu.session_factory",
        "bot.handlers.mood.session_factory",
        "bot.tasks.session_factory",
    ]
    patches = [patch(t, _factory) for t in targets]
    for p in patches:
        p.start()
    try:
        yield _factory
    finally:
        for p in patches:
            p.stop()
