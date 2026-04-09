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
    get_active_course,
    get_doses_taken_today,
    get_or_create_user,
    log_dose,
    start_course,
)
from bot.services.schedule import get_phase
from bot.taskiq_broker import schedule_source
from bot.tasks import schedule_daily_doses, schedule_next_day
from bot.utils.texts import (
    course_cancelled_text,
    course_started_text,
    dose_taken_text,
    menu_text,
)

router = Router()


@router.callback_query(CourseCallback.filter(F.action == "confirm_start"))
async def on_confirm_start(callback: CallbackQuery) -> None:
    async with session_factory() as session:
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
    kb = main_menu_keyboard(has_course=True)
    await callback.message.edit_text(menu_text(), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(CourseCallback.filter(F.action == "confirm_cancel"))
async def on_confirm_cancel(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        active = await get_active_course(session, callback.from_user.id)
        if active:
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

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        now = datetime.datetime.now(tz)

        await log_dose(
            session,
            course_id=callback_data.course_id,
            user_id=callback.from_user.id,
            scheduled_at=now,
            day=callback_data.day,
            phase=callback_data.phase,
        )

        today = now.date()
        taken = await get_doses_taken_today(session, active.id, today)
        await session.commit()

    phase_info = get_phase(callback_data.day)
    await callback.message.edit_text(
        dose_taken_text(taken, phase_info.target_tablets),
        parse_mode="HTML",
    )
    await callback.answer("✅ Отмечено!")
