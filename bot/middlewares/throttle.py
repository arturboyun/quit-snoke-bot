"""Throttling middleware — simple per-user rate limiting."""

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.5) -> None:
        self.rate_limit = rate_limit
        self._timestamps: dict[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        last = self._timestamps[user.id]
        if now - last < self.rate_limit:
            return None

        self._timestamps[user.id] = now
        return await handler(event, data)
