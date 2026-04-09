"""User settings: timezone, wake/sleep times."""

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.db.engine import session_factory
from bot.keyboards.inline import SettingsCallback, main_menu_keyboard, timezone_keyboard
from bot.services.course import get_or_create_user, update_user_settings
from bot.utils.texts import (
    ask_sleep_time_text,
    ask_timezone_text,
    ask_wake_time_text,
    invalid_time_format_text,
    invalid_timezone_text,
    settings_saved_text,
)

router = Router()


class SettingsStates(StatesGroup):
    waiting_timezone = State()
    waiting_wake_time = State()
    waiting_sleep_time = State()


@router.callback_query(SettingsCallback.filter(F.action == "timezone"))
async def on_change_timezone(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(
        ask_timezone_text(),
        reply_markup=timezone_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SettingsStates.waiting_timezone)
    await callback.answer()


@router.callback_query(SettingsCallback.filter(F.action == "wake_time"))
async def on_change_wake(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(ask_wake_time_text(), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_wake_time)
    await callback.answer()


@router.callback_query(SettingsCallback.filter(F.action == "sleep_time"))
async def on_change_sleep(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(ask_sleep_time_text(), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_sleep_time)
    await callback.answer()


@router.message(SettingsStates.waiting_timezone)
async def on_settings_timezone(message: Message, state: FSMContext) -> None:
    tz_name = message.text.strip()
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        await message.answer(invalid_timezone_text(), parse_mode="HTML")
        return

    async with session_factory() as session:
        await update_user_settings(session, message.from_user.id, timezone=tz_name)
        await session.commit()

    await state.clear()
    await message.answer(
        settings_saved_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(SettingsStates.waiting_timezone, F.data.startswith("tz:"))
async def on_settings_timezone_button(callback: CallbackQuery, state: FSMContext) -> None:
    tz_name = callback.data.split(":", 1)[1]
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        await callback.answer(invalid_timezone_text())
        return

    async with session_factory() as session:
        await update_user_settings(session, callback.from_user.id, timezone=tz_name)
        await session.commit()

    await state.clear()
    await callback.message.edit_text(
        f"🌍 Часовой пояс: <b>{tz_name}</b> ✅",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SettingsStates.waiting_wake_time)
async def on_settings_wake(message: Message, state: FSMContext) -> None:
    try:
        t = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return

    async with session_factory() as session:
        await update_user_settings(session, message.from_user.id, wake_time=t)
        await session.commit()

    await state.clear()
    await message.answer(
        settings_saved_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(SettingsStates.waiting_sleep_time)
async def on_settings_sleep(message: Message, state: FSMContext) -> None:
    try:
        t = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return

    async with session_factory() as session:
        await update_user_settings(session, message.from_user.id, sleep_time=t)
        await session.commit()

    await state.clear()
    await message.answer(
        settings_saved_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
