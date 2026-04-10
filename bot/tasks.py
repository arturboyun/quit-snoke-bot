"""TaskIQ tasks — dose reminders, daily schedule, quit-day notifications."""

import datetime
import logging
from zoneinfo import ZoneInfo

from aiogram import Bot

from bot.config import settings
from bot.db.engine import session_factory
from bot.keyboards.inline import dose_taken_keyboard
from bot.models.course import CourseStatus
from bot.services.course import (
    get_active_course,
    get_or_create_user,
    grant_achievement,
    log_missed_doses,
)
from bot.services.schedule import (
    QUIT_DAY,
    get_course_day,
    get_phase,
    get_progress,
    is_first_day_of_phase,
)
from bot.taskiq_broker import broker, schedule_source
from bot.utils.texts import (
    course_completed_text,
    dose_followup_text,
    dose_reminder_text,
    missed_doses_text,
    morning_checkin_text,
    phase_change_text,
    progress_text,
    quit_day_text,
)

# Minutes to wait after a dose reminder before sending a follow-up nudge
FOLLOWUP_DELAY_MINUTES = 15

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

        phase_info = get_phase(day)
        text = dose_reminder_text(day, phase, phase_info.target_display)
        kb = dose_taken_keyboard(course_id=course_id, day=day, phase=phase)
        await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to send dose reminder to user %d", user_id)
    finally:
        await bot.session.close()


@broker.task
async def send_dose_followup(
    user_id: int, course_id: int, day: int, phase: int, dose_number: int
) -> None:
    """Follow-up nudge sent if the user hasn't confirmed a dose."""
    bot = Bot(token=settings.token)
    try:
        async with session_factory() as session:
            course = await get_active_course(session, user_id)
            if not course or course.id != course_id:
                return

            from bot.services.course import get_doses_taken_today

            user = await get_or_create_user(session, user_id)
            tz = ZoneInfo(user.timezone)
            today = datetime.datetime.now(tz).date()
            taken = await get_doses_taken_today(session, course_id, today)

            # User already confirmed this dose (or later ones) — no nudge needed
            if taken >= dose_number:
                return

        phase_info = get_phase(day)
        text = dose_followup_text(day, phase, phase_info.target_display)
        kb = dose_taken_keyboard(course_id=course_id, day=day, phase=phase)
        await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to send dose follow-up to user %d", user_id)
    finally:
        await bot.session.close()


@broker.task
async def schedule_daily_doses(user_id: int) -> None:
    """Daily housekeeping: missed-dose logging, phase/quit-day notifications,
    morning check-in, fallback auto-start, and progress summary.

    Individual dose reminders are NOT scheduled here — they are managed
    by the chain-based ``schedule_next_dose`` / ``handle_dose_timeout`` loop.
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
            await grant_achievement(session, user_id, "course_completed")
            await session.commit()
            bot = Bot(token=settings.token)
            try:
                await bot.send_message(user_id, course_completed_text())
            finally:
                await bot.session.close()
            return

        if day < 1:
            return

        # Log missed doses for all unlogged days (handles multi-day gaps)
        if day > 1:
            total_missed = 0
            first_gap_day = max(1, day - 7)  # look back at most 7 days
            for gap_day in range(first_gap_day, day):
                gap_phase = get_phase(gap_day)
                missed = await log_missed_doses(
                    session,
                    course.id,
                    user_id,
                    day=gap_day,
                    phase=gap_phase.phase,
                    total_expected=gap_phase.min_tablets,  # Phase 5: 1 (not 2)
                )
                total_missed += missed
            if total_missed > 0:
                bot = Bot(token=settings.token)
                try:
                    await bot.send_message(
                        user_id,
                        missed_doses_text(total_missed, day - 1),
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
                        phase_info.target_display,
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

        # Fallback: auto-start dose chain if user doesn't click "Проснулся"
        fallback_dt = datetime.datetime.combine(
            today,
            user.wake_time,
            tzinfo=tz,
        ) + datetime.timedelta(hours=2)
        if fallback_dt > now:
            await auto_start_doses.schedule_by_time(
                schedule_source,
                fallback_dt,
                user_id,
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

        if day > 26:
            return

        # Schedule daily dose calculation 1 minute before wake time tomorrow
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
    """Send morning check-in with wake-up button and mood selection."""
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

    from bot.keyboards.inline import morning_checkin_keyboard

    bot = Bot(token=settings.token)
    try:
        await bot.send_message(
            user_id,
            morning_checkin_text(day),
            reply_markup=morning_checkin_keyboard(),
        )
    except Exception:
        logger.exception("Failed to send morning check-in to user %d", user_id)
    finally:
        await bot.session.close()


@broker.task
async def schedule_next_dose(user_id: int) -> None:
    """Schedule the next dose reminder in the adaptive chain.

    Determines the next dose time based on when the last dose was actually
    taken (not a fixed schedule).  Sends the reminder immediately if the
    time has already arrived, or schedules it for the future.  Also queues
    a follow-up nudge and a timeout handler to advance the chain if the
    user doesn't confirm.
    """
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            return

        user = course.user
        if user is None:
            user = await get_or_create_user(session, user_id)

        tz = ZoneInfo(user.timezone)
        now = datetime.datetime.now(tz)
        today = now.date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            return

        phase_info = get_phase(day)

        from bot.services.course import get_doses_taken_today, get_last_dose_time

        taken = await get_doses_taken_today(session, course.id, today)

        if taken >= phase_info.target_tablets:
            return  # All doses taken for today

        # Determine next dose time from last actual intake
        last_time = await get_last_dose_time(session, course.id, day)

        if last_time is not None:
            last_aware = last_time if last_time.tzinfo else last_time.replace(tzinfo=datetime.UTC)
            next_dt = last_aware.astimezone(tz) + datetime.timedelta(
                minutes=phase_info.interval_minutes,
            )
        else:
            next_dt = now  # First dose of the day — send immediately

        dose_number = taken + 1

        if next_dt <= now:
            # Send immediately
            await send_dose_reminder.kiq(user_id, course.id, day, phase_info.phase)
        else:
            await send_dose_reminder.schedule_by_time(
                schedule_source,
                next_dt,
                user_id,
                course.id,
                day,
                phase_info.phase,
            )

        # Follow-up nudge
        reminder_dt = max(next_dt, now)
        followup_dt = reminder_dt + datetime.timedelta(minutes=FOLLOWUP_DELAY_MINUTES)
        await send_dose_followup.schedule_by_time(
            schedule_source,
            followup_dt,
            user_id,
            course.id,
            day,
            phase_info.phase,
            dose_number,
        )

        # Timeout: advance chain if dose not confirmed within one interval
        timeout_dt = reminder_dt + datetime.timedelta(minutes=phase_info.interval_minutes)
        await handle_dose_timeout.schedule_by_time(
            schedule_source,
            timeout_dt,
            user_id,
            dose_number,
        )


@broker.task
async def handle_dose_timeout(user_id: int, expected_taken: int) -> None:
    """Advance the dose chain when a reminder goes unconfirmed.

    Fires one interval after the last reminder.  If the user already
    confirmed the dose the task is stale and exits.  Otherwise it
    kicks ``schedule_next_dose`` which sends a new reminder immediately
    and schedules the next timeout — effectively reminding the user
    every *interval* until they respond or sleep time arrives.
    """
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            return

        user = course.user
        if user is None:
            user = await get_or_create_user(session, user_id)

        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()

        from bot.services.course import get_doses_taken_today

        taken = await get_doses_taken_today(session, course.id, today)

    if taken >= expected_taken:
        return  # Dose was confirmed, chain already advanced

    # Dose was missed — advance chain (sends a new reminder)
    await schedule_next_dose.kiq(user_id)


@broker.task
async def auto_start_doses(user_id: int) -> None:
    """Fallback: start the dose chain if user didn't click 'Проснулся'.

    Scheduled at wake_time + 2 hours.  If no doses have been taken yet
    today the chain is kicked off automatically.
    """
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            return

        user = course.user
        if user is None:
            user = await get_or_create_user(session, user_id)

        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()

        from bot.services.course import get_doses_taken_today

        taken = await get_doses_taken_today(session, course.id, today)

    if taken == 0:
        await schedule_next_dose.kiq(user_id)
