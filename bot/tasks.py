"""TaskIQ tasks — dose reminders, daily schedule, quit-day notifications."""

import datetime
import logging
from zoneinfo import ZoneInfo

from aiogram import Bot

from bot.config import settings
from bot.db.engine import session_factory
from bot.keyboards.inline import dose_taken_keyboard
from bot.models.course import CourseStatus
from bot.services.course import get_active_course, get_or_create_user, log_missed_doses
from bot.services.schedule import (
    QUIT_DAY,
    calculate_dose_times,
    get_course_day,
    get_phase,
    get_progress,
    is_first_day_of_phase,
)
from bot.taskiq_broker import broker, schedule_source
from bot.utils.texts import (
    course_completed_text,
    dose_reminder_text,
    missed_doses_text,
    morning_checkin_text,
    phase_change_text,
    progress_text,
    quit_day_text,
)

logger = logging.getLogger(__name__)


@broker.task
async def send_dose_reminder(user_id: int, course_id: int, day: int, phase: int) -> None:
    """Send a single dose reminder with a confirmation button."""
    bot = Bot(token=settings.token)
    try:
        async with session_factory() as session:
            course = await get_active_course(session, user_id)
            if not course or course.id != course_id:
                return

            user = await get_or_create_user(session, user_id)
            tz = ZoneInfo(user.timezone)
            now_time = datetime.datetime.now(tz).time()

            # Validate reminder is still within waking hours (settings may have changed)
            if user.sleep_time > user.wake_time:
                if now_time < user.wake_time or now_time >= user.sleep_time:
                    return
            else:
                if user.sleep_time <= now_time < user.wake_time:
                    return

        phase_info = get_phase(day)
        text = dose_reminder_text(day, phase, phase_info.target_tablets)
        kb = dose_taken_keyboard(course_id=course_id, day=day, phase=phase)
        await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to send dose reminder to user %d", user_id)
    finally:
        await bot.session.close()


@broker.task
async def schedule_daily_doses(user_id: int) -> None:
    """Calculate and schedule all dose reminders for the current day.

    This task runs once daily (early morning). It also handles:
    - Logging missed doses from the previous day
    - Phase change notification
    - Quit-day notification on day 5
    - Course completion on day 26
    - Progress summary scheduling
    """
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            return

        user = course.user  # loaded via relationship
        if user is None:
            from bot.services.course import get_or_create_user

            user = await get_or_create_user(session, user_id)

        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)

        # Course ended
        if day > 25:
            course.status = CourseStatus.COMPLETED
            await session.commit()
            bot = Bot(token=settings.token)
            try:
                await bot.send_message(user_id, course_completed_text())
            finally:
                await bot.session.close()
            return

        if day < 1:
            return

        # Log missed doses from previous day
        if day > 1:
            prev_day = day - 1
            prev_phase = get_phase(prev_day)
            missed = await log_missed_doses(
                session,
                course.id,
                user_id,
                day=prev_day,
                phase=prev_phase.phase,
                total_expected=prev_phase.target_tablets,
            )
            if missed > 0:
                bot = Bot(token=settings.token)
                try:
                    await bot.send_message(
                        user_id,
                        missed_doses_text(missed, prev_day),
                        parse_mode="HTML",
                    )
                finally:
                    await bot.session.close()

        # Phase change notification
        if is_first_day_of_phase(day) and day > 1:
            phase_info = get_phase(day)
            bot = Bot(token=settings.token)
            try:
                await bot.send_message(
                    user_id,
                    phase_change_text(
                        phase_info.phase,
                        phase_info.interval_minutes,
                        phase_info.target_tablets,
                    ),
                    parse_mode="HTML",
                )
            finally:
                await bot.session.close()

        # Quit-day reminder
        if day == QUIT_DAY:
            bot = Bot(token=settings.token)
            try:
                await bot.send_message(user_id, quit_day_text())
            finally:
                await bot.session.close()

        # Calculate dose times and schedule each as a separate task
        slots = calculate_dose_times(
            day=day,
            wake_time=user.wake_time,
            sleep_time=user.sleep_time,
            course_start_date=course.start_date,
            timezone=user.timezone,
        )

        now = datetime.datetime.now(tz)

        # Schedule morning check-in (5 min after wake time)
        wake_dt = datetime.datetime.combine(
            today,
            user.wake_time,
            tzinfo=tz,
        ) + datetime.timedelta(minutes=5)
        if wake_dt > now:
            await send_morning_checkin.schedule_by_time(
                schedule_source,
                wake_dt,
                user_id,
            )

        for slot in slots:
            if slot.time <= now:
                continue
            await send_dose_reminder.schedule_by_time(
                schedule_source,
                slot.time,
                user_id,
                course.id,
                slot.day,
                slot.phase,
            )

        # Schedule progress summary near end of day (15 min before sleep)
        summary_dt = datetime.datetime.combine(
            today,
            user.sleep_time,
            tzinfo=tz,
        ) - datetime.timedelta(minutes=15)
        if summary_dt > now:
            await send_progress_summary.schedule_by_time(
                schedule_source,
                summary_dt,
                user_id,
            )

        await session.commit()


@broker.task
async def schedule_next_day(user_id: int) -> None:
    """Called at the end of each day to schedule the next day's daily task.

    This creates a one-shot schedule for tomorrow's schedule_daily_doses.
    """
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            return

        user = course.user
        if user is None:
            from bot.services.course import get_or_create_user

            user = await get_or_create_user(session, user_id)

        tz = ZoneInfo(user.timezone)
        tomorrow = datetime.datetime.now(tz).date() + datetime.timedelta(days=1)
        day = get_course_day(course.start_date, tomorrow)

        if day > 25:
            return

        # Schedule daily dose calculation 1 minute after wake time tomorrow
        wake_dt = datetime.datetime.combine(
            tomorrow,
            user.wake_time,
            tzinfo=tz,
        ) - datetime.timedelta(minutes=1)

        await schedule_daily_doses.schedule_by_time(
            schedule_source,
            wake_dt,
            user_id,
        )

        # Also schedule this task again for end of tomorrow
        sleep_dt = datetime.datetime.combine(tomorrow, user.sleep_time, tzinfo=tz)
        await schedule_next_day.schedule_by_time(
            schedule_source,
            sleep_dt,
            user_id,
        )


@broker.task
async def send_progress_summary(user_id: int) -> None:
    """Send daily progress summary to the user."""
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            return

        user = course.user
        if user is None:
            from bot.services.course import get_or_create_user

            user = await get_or_create_user(session, user_id)

        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            return

        from bot.services.course import get_doses_taken_today

        taken = await get_doses_taken_today(session, course.id, today)
        stats = get_progress(day, taken)

        # Add smoke-free days for day >= 5
        if day >= QUIT_DAY:
            from bot.services.course import get_relapse_stats

            relapse_stats = await get_relapse_stats(session, user_id)
            if relapse_stats["total_cigarettes"] == 0:
                stats["smoke_free_days"] = max(0, day - QUIT_DAY)

    bot = Bot(token=settings.token)
    try:
        await bot.send_message(user_id, progress_text(stats), parse_mode="HTML")
    finally:
        await bot.session.close()


@broker.task
async def send_morning_checkin(user_id: int) -> None:
    """Send morning check-in with mood buttons."""
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            return

        user = course.user
        if user is None:
            from bot.services.course import get_or_create_user

            user = await get_or_create_user(session, user_id)

        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            return

    from bot.keyboards.inline import mood_keyboard

    bot = Bot(token=settings.token)
    try:
        await bot.send_message(
            user_id,
            morning_checkin_text(day),
            reply_markup=mood_keyboard(),
        )
    except Exception:
        logger.exception("Failed to send morning check-in to user %d", user_id)
    finally:
        await bot.session.close()
