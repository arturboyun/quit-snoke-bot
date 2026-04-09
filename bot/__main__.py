"""Bot entry point."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.handlers import main_router
from bot.middlewares.throttle import ThrottleMiddleware
from bot.taskiq_broker import broker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=settings.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.middleware(ThrottleMiddleware())
    dp.include_router(main_router)

    # Start TaskIQ broker (client side — for sending tasks)
    await broker.startup()

    await bot.delete_my_commands()

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        await broker.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
