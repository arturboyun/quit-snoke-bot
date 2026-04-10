from aiogram import Router

from bot.dialogs.menu import menu_dialog

dialog_router = Router()
dialog_router.include_router(menu_dialog)
