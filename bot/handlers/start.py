"""Onboarding: /start with FSM for timezone, wake/sleep time setup."""

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.db.engine import session_factory
from bot.keyboards.inline import main_menu_keyboard, timezone_keyboard
from bot.models.user import User
from bot.services.course import (
    get_active_course,
    get_or_create_user,
    save_smoking_profile,
    update_user_settings,
)
from bot.utils.texts import (
    ask_cigarettes_per_day_text,
    ask_pack_price_text,
    ask_sleep_time_text,
    ask_timezone_text,
    ask_wake_time_text,
    invalid_time_format_text,
    invalid_timezone_text,
    settings_saved_text,
    welcome_text,
)

router = Router()


class OnboardingStates(StatesGroup):
    waiting_timezone = State()
    waiting_wake_time = State()
    waiting_sleep_time = State()
    waiting_cigarettes_per_day = State()
    waiting_pack_price = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    async with session_factory() as session:
        existing = await session.get(User, message.from_user.id)
        user = await get_or_create_user(session, message.from_user.id)
        await session.commit()

    if existing:
        await state.clear()
        async with session_factory() as session:
            course = await get_active_course(session, message.from_user.id)
        await message.answer(
            welcome_text(),
            reply_markup=main_menu_keyboard(has_course=course is not None),
            parse_mode="HTML",
        )
        return

    await message.answer(welcome_text(), parse_mode="HTML")
    await message.answer(
        ask_timezone_text(),
        reply_markup=timezone_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OnboardingStates.waiting_timezone)


@router.callback_query(OnboardingStates.waiting_timezone, F.data.startswith("tz:"))
async def on_timezone_button(callback: CallbackQuery, state: FSMContext) -> None:
    tz_name = callback.data.split(":", 1)[1]
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        await callback.answer(invalid_timezone_text())
        return

    await state.update_data(timezone=tz_name)
    await callback.message.edit_text(
        f"🌍 Часовой пояс: <b>{tz_name}</b> ✅",
        parse_mode="HTML",
    )
    await callback.message.answer(ask_wake_time_text(), parse_mode="HTML")
    await state.set_state(OnboardingStates.waiting_wake_time)
    await callback.answer()


@router.message(OnboardingStates.waiting_timezone)
async def on_timezone_text(message: Message, state: FSMContext) -> None:
    tz_name = message.text.strip()
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        await message.answer(invalid_timezone_text(), parse_mode="HTML")
        return

    await state.update_data(timezone=tz_name)
    await message.answer(ask_wake_time_text(), parse_mode="HTML")
    await state.set_state(OnboardingStates.waiting_wake_time)


@router.message(OnboardingStates.waiting_wake_time)
async def on_wake_time(message: Message, state: FSMContext) -> None:
    try:
        t = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return

    await state.update_data(wake_time=t.isoformat())
    await message.answer(ask_sleep_time_text(), parse_mode="HTML")
    await state.set_state(OnboardingStates.waiting_sleep_time)


@router.message(OnboardingStates.waiting_sleep_time)
async def on_sleep_time(message: Message, state: FSMContext) -> None:
    try:
        t = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer(invalid_time_format_text(), parse_mode="HTML")
        return

    data = await state.get_data()
    tz_name = data["timezone"]
    wake_time = datetime.time.fromisoformat(data["wake_time"])

    async with session_factory() as session:
        await update_user_settings(
            session,
            message.from_user.id,
            timezone=tz_name,
            wake_time=wake_time,
            sleep_time=t,
        )
        await session.commit()

    await state.update_data(sleep_time=t.isoformat())
    await message.answer(ask_cigarettes_per_day_text(), parse_mode="HTML")
    await state.set_state(OnboardingStates.waiting_cigarettes_per_day)


@router.message(OnboardingStates.waiting_cigarettes_per_day)
async def on_onboard_cigarettes(message: Message, state: FSMContext) -> None:
    try:
        count = int(message.text.strip())
        if count < 1 or count > 200:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Отправь число от 1 до 200.", parse_mode="HTML")
        return

    await state.update_data(cigarettes_per_day=count)
    await message.answer(ask_pack_price_text(), parse_mode="HTML")
    await state.set_state(OnboardingStates.waiting_pack_price)


@router.message(OnboardingStates.waiting_pack_price)
async def on_onboard_pack_price(message: Message, state: FSMContext) -> None:
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0 or price > 100000:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Отправь цену числом, например: <b>150</b>", parse_mode="HTML")
        return

    data = await state.get_data()

    async with session_factory() as session:
        await save_smoking_profile(
            session,
            message.from_user.id,
            cigarettes_per_day=data["cigarettes_per_day"],
            pack_price=price,
        )
        await session.commit()

    await state.clear()
    await message.answer(
        settings_saved_text(),
        reply_markup=main_menu_keyboard(has_course=False),
        parse_mode="HTML",
    )
