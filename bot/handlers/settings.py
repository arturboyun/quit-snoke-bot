"""User settings: timezone, wake/sleep times, smoking profile."""

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode

from bot.db.engine import session_factory
from bot.dialogs.menu import MenuSG
from bot.keyboards.inline import SettingsCallback, timezone_keyboard
from bot.services.course import (
    get_active_course,
    save_smoking_profile,
    update_user_settings,
)
from bot.taskiq_broker import schedule_source
from bot.tasks import schedule_daily_doses, schedule_next_day
from bot.utils.texts import (
    ask_cigarettes_per_day_text,
    ask_pack_price_text,
    ask_sleep_time_text,
    ask_timezone_text,
    ask_wake_time_text,
    invalid_time_format_text,
    invalid_timezone_text,
    settings_saved_text,
    smoking_profile_saved_text,
)

router = Router()


class SettingsStates(StatesGroup):
    waiting_timezone = State()
    waiting_wake_time = State()
    waiting_sleep_time = State()
    waiting_cigarettes_per_day = State()
    waiting_pack_price = State()


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
async def on_settings_timezone(message: Message, state: FSMContext, dialog_manager: DialogManager) -> None:
    if not message.text:
        await message.answer(invalid_timezone_text(), parse_mode="HTML")
        return
    tz_name = message.text.strip()
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        await message.answer(invalid_timezone_text(), parse_mode="HTML")
        return

    async with session_factory() as session:
        await update_user_settings(session, message.from_user.id, timezone=tz_name)
        await session.commit()
        course = await get_active_course(session, message.from_user.id)

    has_course = course is not None
    if has_course:
        await schedule_source.startup()
        await schedule_daily_doses.kiq(message.from_user.id)
        await schedule_next_day.kiq(message.from_user.id)

    await state.clear()
    await message.answer(settings_saved_text(), parse_mode="HTML")
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


@router.callback_query(SettingsStates.waiting_timezone, F.data.startswith("tz:"))
async def on_settings_timezone_button(callback: CallbackQuery, state: FSMContext, dialog_manager: DialogManager) -> None:
    tz_name = callback.data.split(":", 1)[1]
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        await callback.answer(invalid_timezone_text())
        return

    async with session_factory() as session:
        await update_user_settings(session, callback.from_user.id, timezone=tz_name)
        await session.commit()
        course = await get_active_course(session, callback.from_user.id)

    has_course = course is not None
    if has_course:
        await schedule_source.startup()
        await schedule_daily_doses.kiq(callback.from_user.id)
        await schedule_next_day.kiq(callback.from_user.id)

    await state.clear()
    await callback.message.edit_text(
        f"🌍 Часовой пояс: <b>{tz_name}</b> ✅",
        parse_mode="HTML",
    )
    await callback.answer()
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


@router.message(SettingsStates.waiting_wake_time)
async def on_settings_wake(message: Message, state: FSMContext, dialog_manager: DialogManager) -> None:
    if not message.text:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return
    try:
        t = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return

    async with session_factory() as session:
        await update_user_settings(session, message.from_user.id, wake_time=t)
        await session.commit()
        course = await get_active_course(session, message.from_user.id)

    has_course = course is not None
    if has_course:
        await schedule_source.startup()
        await schedule_daily_doses.kiq(message.from_user.id)
        await schedule_next_day.kiq(message.from_user.id)

    await state.clear()
    await message.answer(settings_saved_text(), parse_mode="HTML")
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


@router.message(SettingsStates.waiting_sleep_time)
async def on_settings_sleep(message: Message, state: FSMContext, dialog_manager: DialogManager) -> None:
    if not message.text:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return
    try:
        t = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return

    async with session_factory() as session:
        await update_user_settings(session, message.from_user.id, sleep_time=t)
        await session.commit()
        course = await get_active_course(session, message.from_user.id)

    has_course = course is not None
    if has_course:
        await schedule_source.startup()
        await schedule_daily_doses.kiq(message.from_user.id)
        await schedule_next_day.kiq(message.from_user.id)

    await state.clear()
    await message.answer(settings_saved_text(), parse_mode="HTML")
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


# ── Smoking Profile ──────────────────────────────────────────────────────────


@router.callback_query(SettingsCallback.filter(F.action == "smoking_profile"))
async def on_change_smoking_profile(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(ask_cigarettes_per_day_text(), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_cigarettes_per_day)
    await callback.answer()


@router.message(SettingsStates.waiting_cigarettes_per_day)
async def on_cigarettes_per_day(message: Message, state: FSMContext) -> None:
    try:
        count = int(message.text.strip())
        if count < 1 or count > 200:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Отправь число от 1 до 200.", parse_mode="HTML")
        return

    await state.update_data(cigarettes_per_day=count)
    await message.answer(ask_pack_price_text(), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_pack_price)


@router.message(SettingsStates.waiting_pack_price)
async def on_pack_price(message: Message, state: FSMContext, dialog_manager: DialogManager) -> None:
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0 or price > 100000:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Отправь цену числом, например: <b>150</b>", parse_mode="HTML")
        return

    data = await state.get_data()
    cigarettes_per_day = data["cigarettes_per_day"]

    async with session_factory() as session:
        await save_smoking_profile(
            session,
            message.from_user.id,
            cigarettes_per_day=cigarettes_per_day,
            pack_price=price,
        )
        await session.commit()

    await state.clear()
    await message.answer(smoking_profile_saved_text(), parse_mode="HTML")
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)
