"""Bot entry point."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import ExceptionTypeFilter
from aiogram_dialog import ShowMode, StartMode, setup_dialogs
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState
from sqlalchemy import select

from bot.config import settings
from bot.db.engine import session_factory
from bot.dialogs import dialog_router
from bot.dialogs.menu import MenuSG
from bot.handlers import main_router
from bot.middlewares.throttle import ThrottleMiddleware
from bot.models.course import Course, CourseStatus
from bot.taskiq_broker import broker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _reschedule_active_courses() -> None:
    """Re-schedule dose reminders for all active courses (recovery after restart)."""
    from bot.tasks import schedule_daily_doses, schedule_next_day

    async with session_factory() as session:
        stmt = select(Course.user_id).where(Course.status == CourseStatus.ACTIVE)
        result = await session.execute(stmt)
        user_ids = result.scalars().all()

    for uid in user_ids:
        await schedule_daily_doses.kiq(uid)
        await schedule_next_day.kiq(uid)

    if user_ids:
        logger.info("Re-scheduled %d active course(s) after startup", len(user_ids))


async def main() -> None:
    bot = Bot(
        token=settings.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.middleware(ThrottleMiddleware())
    dp.include_router(main_router)
    dp.include_router(dialog_router)

    # Handle stale dialog buttons after bot restart
    async def on_unknown_intent(event, dialog_manager):
        await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND)

    async def on_unknown_state(event, dialog_manager):
        await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND)

    dp.errors.register(on_unknown_intent, ExceptionTypeFilter(UnknownIntent))
    dp.errors.register(on_unknown_state, ExceptionTypeFilter(UnknownState))

    setup_dialogs(dp)

    # Start TaskIQ broker (client side — for sending tasks)
    await broker.startup()

    # Recovery: re-schedule all active courses after restart
    await _reschedule_active_courses()

    await bot.delete_my_commands()

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        await broker.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
