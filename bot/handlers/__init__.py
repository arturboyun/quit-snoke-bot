from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.course import router as course_router
from bot.handlers.menu import router as menu_router
from bot.handlers.progress import router as progress_router
from bot.handlers.settings import router as settings_router

main_router = Router()
main_router.include_routers(
    start_router, course_router, menu_router, progress_router, settings_router,
)
