"""Mood check-in callback handler."""

from aiogram import Router
from aiogram.types import CallbackQuery

from bot.db.engine import session_factory
from bot.keyboards.inline import MoodCallback
from bot.services.course import log_mood
from bot.utils.texts import mood_logged_text

router = Router()


@router.callback_query(MoodCallback.filter())
async def on_mood_selected(callback: CallbackQuery, callback_data: MoodCallback) -> None:
    async with session_factory() as session:
        await log_mood(session, callback.from_user.id, callback_data.value)
        await session.commit()

    await callback.message.edit_text(
        mood_logged_text(callback_data.value),
        parse_mode="HTML",
    )
    await callback.answer()
