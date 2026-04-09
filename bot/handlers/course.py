"""Course management: confirm start/cancel, dose confirmation."""

import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.db.engine import session_factory
from bot.keyboards.inline import (
    CourseCallback,
    DoseCallback,
    main_menu_keyboard,
)
from bot.models.course import CourseStatus
from bot.services.course import (
    check_and_grant_achievements,
    get_active_course,
    get_doses_taken_today,
    get_last_dose_time,
    get_or_create_user,
    log_dose,
    start_course,
)
from bot.services.schedule import calculate_remaining_doses_today, get_phase
from bot.taskiq_broker import schedule_source
from bot.tasks import schedule_daily_doses, schedule_next_day
from bot.utils.texts import (
    course_cancelled_text,
    course_started_text,
    dose_taken_text,
    dose_too_soon_text,
    menu_text,
)

router = Router()


@router.callback_query(CourseCallback.filter(F.action == "confirm_start"))
async def on_confirm_start(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        # Double-click protection: check if course was already created
        active = await get_active_course(session, callback.from_user.id)
        if active:
            await callback.answer("Курс уже создан", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        today = datetime.datetime.now(ZoneInfo(user.timezone)).date()
        await start_course(session, callback.from_user.id, today)
        await session.commit()

    await callback.message.edit_text(
        course_started_text(today.isoformat()),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(has_course=True),
    )

    await schedule_source.startup()
    await schedule_daily_doses.kiq(callback.from_user.id)
    await schedule_next_day.kiq(callback.from_user.id)
    await callback.answer()


@router.callback_query(CourseCallback.filter(F.action == "cancel"))
async def on_cancel_action(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
    kb = main_menu_keyboard(has_course=course is not None)
    await callback.message.edit_text(menu_text(), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(CourseCallback.filter(F.action == "confirm_cancel"))
async def on_confirm_cancel(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        active = await get_active_course(session, callback.from_user.id)
        if not active:
            await callback.answer("Нет активного курса", show_alert=True)
            return
        active.status = CourseStatus.CANCELLED
        await session.commit()

    await callback.message.edit_text(
        course_cancelled_text(),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(has_course=False),
    )
    await callback.answer()


@router.callback_query(DoseCallback.filter(F.action == "taken"))
async def on_dose_taken(callback: CallbackQuery, callback_data: DoseCallback) -> None:
    async with session_factory() as session:
        active = await get_active_course(session, callback.from_user.id)
        if not active:
            await callback.answer("Курс не найден", show_alert=True)
            return

        # Stale button protection: verify course_id matches active course
        if active.id != callback_data.course_id:
            await callback.answer("Эта кнопка от старого курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        now = datetime.datetime.now(tz)
        today = now.date()

        # Waking hours check
        now_time = now.time()
        if user.sleep_time > user.wake_time:
            if now_time < user.wake_time or now_time >= user.sleep_time:
                await callback.answer(
                    "Сейчас время сна — таблетку принимать не нужно",
                    show_alert=True,
                )
                return
        else:
            if user.sleep_time <= now_time < user.wake_time:
                await callback.answer(
                    "Сейчас время сна — таблетку принимать не нужно",
                    show_alert=True,
                )
                return

        phase_info = get_phase(callback_data.day)

        # Overdose protection: don't exceed target_tablets for the day
        taken = await get_doses_taken_today(session, active.id, today)
        if taken >= phase_info.target_tablets:
            await callback.answer(
                f"Сегодня уже принято {taken}/{phase_info.target_display} таблеток",
                show_alert=True,
            )
            return

        # Check minimum interval since last dose
        last_time = await get_last_dose_time(session, active.id, callback_data.day)
        if last_time is not None:
            last_aware = last_time if last_time.tzinfo else last_time.replace(tzinfo=datetime.UTC)
            elapsed = (
                now.astimezone(datetime.UTC) - last_aware.astimezone(datetime.UTC)
            ).total_seconds()
            min_interval = phase_info.interval_minutes * 60
            if elapsed < min_interval:
                minutes_left = int((min_interval - elapsed) / 60) + 1
                await callback.answer(
                    dose_too_soon_text(minutes_left),
                    show_alert=True,
                )
                return

        await log_dose(
            session,
            course_id=callback_data.course_id,
            user_id=callback.from_user.id,
            scheduled_at=now,
            day=callback_data.day,
            phase=callback_data.phase,
        )

        taken = await get_doses_taken_today(session, active.id, today)
        await check_and_grant_achievements(
            session, callback.from_user.id, timezone=user.timezone
        )
        await session.commit()

    # Calculate next dose time
    remaining = calculate_remaining_doses_today(
        day=callback_data.day,
        wake_time=user.wake_time,
        sleep_time=user.sleep_time,
        course_start_date=active.start_date,
        timezone=user.timezone,
        now=now,
    )
    next_time = remaining[0].time.strftime("%H:%M") if remaining else None

    await callback.message.edit_text(
        dose_taken_text(taken, phase_info.target_display, next_time),
        parse_mode="HTML",
    )
    await callback.answer("✅ Отмечено!")
