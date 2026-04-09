import datetime
import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Patch bot.db.engine.session_factory to use in-memory SQLite."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def _factory():
        async with factory() as session:
            yield session

    with patch("bot.db.engine.session_factory", _factory):
        yield _factory
