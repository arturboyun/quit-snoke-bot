"""Main menu: inline keyboard with quick access to all features."""

import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.db.engine import session_factory
from bot.keyboards.inline import (
    MenuCallback,
    confirm_cancel_keyboard,
    confirm_start_keyboard,
    main_menu_keyboard,
    settings_keyboard,
)
from bot.services.course import (
    get_active_course,
    get_doses_taken_today,
    get_or_create_user,
    log_dose,
    start_course,
)
from bot.services.schedule import (
    calculate_dose_times,
    get_course_day,
    get_phase,
    get_progress,
)
from bot.taskiq_broker import schedule_source
from bot.tasks import schedule_daily_doses, schedule_next_day
from bot.utils.texts import (
    already_has_course_text,
    course_started_text,
    dose_taken_text,
    help_text,
    menu_text,
    progress_text,
    settings_menu_text,
    today_schedule_text,
)

router = Router()


async def _safe_edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, parse_mode="HTML", **kwargs)
    except TelegramBadRequest:
        pass


async def _menu_kb(user_id: int) -> main_menu_keyboard:
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
    return main_menu_keyboard(has_course=course is not None)


@router.callback_query(MenuCallback.filter(F.action == "back"))
async def on_menu_back(callback: CallbackQuery) -> None:
    kb = await _menu_kb(callback.from_user.id)
    await _safe_edit(callback, menu_text(), reply_markup=kb)
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "start_course"))
async def on_menu_start_course(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        active = await get_active_course(session, callback.from_user.id)
        if active:
            await _safe_edit(
                callback,
                already_has_course_text(),
                reply_markup=confirm_start_keyboard(),
            )
            await callback.answer()
            return

        user = await get_or_create_user(session, callback.from_user.id)
        today = datetime.datetime.now(ZoneInfo(user.timezone)).date()
        await start_course(session, callback.from_user.id, today)
        await session.commit()

    await _safe_edit(
        callback,
        course_started_text(today.isoformat()),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()

    await schedule_source.startup()
    await schedule_daily_doses.kiq(callback.from_user.id)
    await schedule_next_day.kiq(callback.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "cancel_course"))
async def on_menu_cancel_course(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        active = await get_active_course(session, callback.from_user.id)
        if not active:
            await callback.answer("Нет активного курса", show_alert=True)
            return

    await _safe_edit(
        callback,
        "Уверен, что хочешь отменить текущий курс?",
        reply_markup=confirm_cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "take_dose"))
async def on_menu_take_dose(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        now = datetime.datetime.now(tz)
        today = now.date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            await callback.answer("Курс завершён", show_alert=True)
            return

        phase_info = get_phase(day)

        taken = await get_doses_taken_today(session, course.id, today)
        if taken >= phase_info.target_tablets:
            await callback.answer(
                f"Сегодня уже принято {taken}/{phase_info.target_tablets} таблеток",
                show_alert=True,
            )
            return

        await log_dose(
            session,
            course_id=course.id,
            user_id=callback.from_user.id,
            scheduled_at=now,
            day=day,
            phase=phase_info.phase,
        )
        taken = await get_doses_taken_today(session, course.id, today)
        await session.commit()

    await _safe_edit(
        callback,
        dose_taken_text(taken, phase_info.target_tablets),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer("✅ Отмечено!")


@router.callback_query(MenuCallback.filter(F.action == "progress"))
async def on_menu_progress(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            await callback.answer("Курс завершён", show_alert=True)
            return

        taken = await get_doses_taken_today(session, course.id, today)

    stats = get_progress(day, taken)
    await _safe_edit(
        callback,
        progress_text(stats),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "schedule"))
async def on_menu_schedule(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            await callback.answer("Курс завершён", show_alert=True)
            return

    phase_info = get_phase(day)
    slots = calculate_dose_times(
        day=day,
        wake_time=user.wake_time,
        sleep_time=user.sleep_time,
        course_start_date=course.start_date,
        timezone=user.timezone,
    )
    times = [s.time.strftime("%H:%M") for s in slots]

    await _safe_edit(
        callback,
        today_schedule_text(day, phase_info.phase, times, phase_info.target_tablets),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "settings"))
async def on_menu_settings(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        user = await get_or_create_user(session, callback.from_user.id)

    await _safe_edit(
        callback,
        settings_menu_text(
            user.timezone,
            user.wake_time.strftime("%H:%M"),
            user.sleep_time.strftime("%H:%M"),
        ),
        reply_markup=settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "help"))
async def on_menu_help(callback: CallbackQuery) -> None:
    kb = await _menu_kb(callback.from_user.id)
    await _safe_edit(callback, help_text(), reply_markup=kb)
    await callback.answer()
