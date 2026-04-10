"""Tests for TaskIQ tasks — dose reminders, daily scheduling, progress summary."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.course import (
    get_active_course,
    get_or_create_user,
    log_dose,
    start_course,
)


def _bot_mock():
    """Create a mock Bot with async context manager for session."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.session = MagicMock()
    bot.session.close = AsyncMock()
    return bot


class TestSendDoseReminder:
    @patch("bot.tasks.datetime")
    @patch("bot.tasks.Bot")
    async def test_sends_message(self, mock_bot_cls, mock_dt, mock_session_factory) -> None:
        from bot.tasks import send_dose_reminder

        # Fix time to midday so waking-hours check passes
        mock_dt.datetime.now.return_value = datetime.datetime(
            2026, 1, 3, 12, 0, tzinfo=datetime.UTC
        )
        mock_dt.datetime.combine = datetime.datetime.combine

        bot = _bot_mock()
        mock_bot_cls.return_value = bot

        async with mock_session_factory() as session:
            await get_or_create_user(session, 111)
            await start_course(session, 111, datetime.date.today())
            await session.commit()

        # Get the actual course id
        async with mock_session_factory() as session:
            course = await get_active_course(session, 111)
            course_id = course.id

        await send_dose_reminder(user_id=111, course_id=course_id, day=3, phase=1)

        bot.send_message.assert_called_once()
        args = bot.send_message.call_args
        assert args[0][0] == 111
        assert "3/25" in args[0][1]
        # Should include keyboard
        assert args[1].get("reply_markup") is not None
        bot.session.close.assert_called_once()

    @patch("bot.tasks.datetime")
    @patch("bot.tasks.Bot")
    async def test_handles_exception(self, mock_bot_cls, mock_dt, mock_session_factory) -> None:
        from bot.tasks import send_dose_reminder

        mock_dt.datetime.now.return_value = datetime.datetime(
            2026, 1, 1, 12, 0, tzinfo=datetime.UTC
        )
        mock_dt.datetime.combine = datetime.datetime.combine

        bot = _bot_mock()
        bot.send_message = AsyncMock(side_effect=Exception("network error"))
        mock_bot_cls.return_value = bot

        async with mock_session_factory() as session:
            await get_or_create_user(session, 111)
            await start_course(session, 111, datetime.date.today())
            await session.commit()

        async with mock_session_factory() as session:
            course = await get_active_course(session, 111)
            course_id = course.id

        # Should not raise
        await send_dose_reminder(user_id=111, course_id=course_id, day=1, phase=1)
        bot.session.close.assert_called_once()


class TestScheduleDailyDoses:
    @patch("bot.tasks.Bot")
    async def test_no_course_returns_early(
        self,
        mock_bot_cls,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        async with mock_session_factory() as session:
            await get_or_create_user(session, 600)
            await session.commit()

        await schedule_daily_doses(user_id=600)

    @patch("bot.tasks.datetime")
    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_progress_summary")
    @patch("bot.tasks.send_morning_checkin")
    @patch("bot.tasks.auto_start_doses")
    @patch("bot.tasks.Bot")
    async def test_schedules_future_doses(
        self,
        mock_bot_cls,
        mock_auto_start,
        mock_checkin,
        mock_summary,
        mock_sched_src,
        mock_dt,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        # Fix time to midday so day calculation is stable across timezones
        fixed_now = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta

        mock_checkin.schedule_by_time = AsyncMock()
        mock_summary.schedule_by_time = AsyncMock()
        mock_auto_start.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 601)
            await start_course(session, 601, datetime.date(2026, 1, 1))
            await session.commit()

        await schedule_daily_doses(user_id=601)
        # schedule_daily_doses no longer schedules doses directly;
        # it schedules morning check-in, fallback auto-start, and progress summary

    @patch("bot.tasks.Bot")
    async def test_course_over_25_completes(
        self,
        mock_bot_cls,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        bot = _bot_mock()
        mock_bot_cls.return_value = bot

        async with mock_session_factory() as session:
            await get_or_create_user(session, 602)
            # Course started 26 days ago — day > 25
            await start_course(
                session,
                602,
                datetime.date.today() - datetime.timedelta(days=26),
            )
            await session.commit()

        await schedule_daily_doses(user_id=602)

        # Should have sent completion message
        bot.send_message.assert_called_once()
        assert "Поздравляю" in bot.send_message.call_args[0][1]
        bot.session.close.assert_called_once()

        # Course should be marked as completed
        async with mock_session_factory() as session:
            course = await get_active_course(session, 602)
            assert course is None  # no longer active

    @patch("bot.tasks.datetime")
    @patch("bot.tasks.Bot")
    async def test_day_before_start_returns_early(
        self,
        mock_bot_cls,
        mock_dt,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        # Fix time so day calculation is stable across timezones
        fixed_now = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta

        async with mock_session_factory() as session:
            await get_or_create_user(session, 603)
            # Course starts tomorrow — day < 1
            await start_course(
                session,
                603,
                datetime.date(2026, 1, 2),
            )
            await session.commit()

        await schedule_daily_doses(user_id=603)
        # No bot messages, no errors

    @patch("bot.tasks.datetime")
    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_progress_summary")
    @patch("bot.tasks.send_morning_checkin")
    @patch("bot.tasks.auto_start_doses")
    @patch("bot.tasks.Bot")
    async def test_quit_day_sends_message(
        self,
        mock_bot_cls,
        mock_auto_start,
        mock_checkin,
        mock_summary,
        mock_sched_src,
        mock_dt,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        # Fix time to midday on Jan 5 so day=5 (quit day)
        fixed_now = datetime.datetime(2026, 1, 5, 12, 0, tzinfo=datetime.UTC)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta

        bot = _bot_mock()
        mock_bot_cls.return_value = bot
        mock_checkin.schedule_by_time = AsyncMock()
        mock_summary.schedule_by_time = AsyncMock()
        mock_auto_start.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 604)
            # Day 5 is quit day: start_date=Jan 1, today=Jan 5
            await start_course(
                session,
                604,
                datetime.date(2026, 1, 1),
            )
            await session.commit()

        await schedule_daily_doses(user_id=604)
        # Should have sent quit day message
        bot.send_message.assert_called()
        messages = [call[0][1] for call in bot.send_message.call_args_list]
        assert any("ОТКАЗ" in m for m in messages)


class TestScheduleNextDay:
    @patch("bot.tasks.schedule_daily_doses")
    @patch("bot.tasks.schedule_source")
    async def test_no_course_returns_early(
        self,
        mock_source,
        mock_daily,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_next_day

        async with mock_session_factory() as session:
            await get_or_create_user(session, 700)
            await session.commit()

        await schedule_next_day(user_id=700)
        mock_daily.schedule_by_time.assert_not_called()

    @patch("bot.tasks.schedule_daily_doses")
    @patch("bot.tasks.schedule_source")
    async def test_schedules_next_day(
        self,
        mock_source,
        mock_daily,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_next_day as _schedule_next_day

        mock_daily.schedule_by_time = AsyncMock()
        # schedule_next_day also calls schedule_next_day.schedule_by_time
        with patch.object(_schedule_next_day, "schedule_by_time", new=AsyncMock()):
            async with mock_session_factory() as session:
                await get_or_create_user(session, 701)
                await start_course(session, 701, datetime.date.today())
                await session.commit()

            await _schedule_next_day(user_id=701)
            mock_daily.schedule_by_time.assert_called_once()

    @patch("bot.tasks.schedule_daily_doses")
    @patch("bot.tasks.schedule_source")
    async def test_day_over_25_returns_early(
        self,
        mock_source,
        mock_daily,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_next_day

        mock_daily.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 702)
            # Tomorrow would be day 27
            await start_course(
                session,
                702,
                datetime.date.today() - datetime.timedelta(days=25),
            )
            await session.commit()

        await schedule_next_day(user_id=702)
        mock_daily.schedule_by_time.assert_not_called()


class TestSendProgressSummary:
    @patch("bot.tasks.Bot")
    async def test_no_course_returns(self, mock_bot_cls, mock_session_factory) -> None:
        from bot.tasks import send_progress_summary

        async with mock_session_factory() as session:
            await get_or_create_user(session, 800)
            await session.commit()

        await send_progress_summary(user_id=800)
        mock_bot_cls.return_value.send_message.assert_not_called()

    @patch("bot.tasks.Bot")
    async def test_sends_progress(self, mock_bot_cls, mock_session_factory) -> None:
        from bot.tasks import send_progress_summary

        bot = _bot_mock()
        mock_bot_cls.return_value = bot

        async with mock_session_factory() as session:
            await get_or_create_user(session, 801)
            await start_course(session, 801, datetime.date.today())
            await session.commit()

        await send_progress_summary(user_id=801)
        bot.send_message.assert_called_once()
        assert "Прогресс" in bot.send_message.call_args[0][1]
        bot.session.close.assert_called_once()

    @patch("bot.tasks.Bot")
    async def test_course_over_returns(self, mock_bot_cls, mock_session_factory) -> None:
        from bot.tasks import send_progress_summary

        bot = _bot_mock()
        mock_bot_cls.return_value = bot

        async with mock_session_factory() as session:
            await get_or_create_user(session, 802)
            await start_course(
                session,
                802,
                datetime.date.today() - datetime.timedelta(days=30),
            )
            await session.commit()

        await send_progress_summary(user_id=802)
        bot.send_message.assert_not_called()


class TestScheduleNextDose:
    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_dose_followup")
    @patch("bot.tasks.send_dose_reminder")
    @patch("bot.tasks.handle_dose_timeout")
    async def test_no_course_returns(
        self, mock_timeout, mock_send, mock_followup, mock_source, mock_session_factory
    ) -> None:
        from bot.tasks import schedule_next_dose

        mock_send.kiq = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 900)
            await session.commit()

        await schedule_next_dose(user_id=900)
        mock_send.kiq.assert_not_called()

    @patch("bot.tasks.datetime")
    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_dose_followup")
    @patch("bot.tasks.send_dose_reminder")
    @patch("bot.tasks.handle_dose_timeout")
    async def test_first_dose_sends_immediately(
        self, mock_timeout, mock_send, mock_followup, mock_source, mock_dt, mock_session_factory
    ) -> None:
        from bot.tasks import schedule_next_dose

        fixed_now = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=datetime.UTC)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta
        mock_dt.UTC = datetime.UTC

        mock_send.kiq = AsyncMock()
        mock_send.schedule_by_time = AsyncMock()
        mock_followup.schedule_by_time = AsyncMock()
        mock_timeout.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 901)
            await start_course(session, 901, datetime.date(2026, 1, 1))
            await session.commit()

        await schedule_next_dose(user_id=901)
        # First dose: no previous dose → send immediately
        mock_send.kiq.assert_called_once()
        # Timeout and followup should be scheduled
        mock_timeout.schedule_by_time.assert_called_once()
        mock_followup.schedule_by_time.assert_called_once()

    @patch("bot.tasks.datetime")
    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_dose_followup")
    @patch("bot.tasks.send_dose_reminder")
    @patch("bot.tasks.handle_dose_timeout")
    async def test_next_dose_scheduled_after_taken(
        self, mock_timeout, mock_send, mock_followup, mock_source, mock_dt, mock_session_factory
    ) -> None:
        from bot.tasks import schedule_next_dose

        fixed_now = datetime.datetime(2026, 1, 1, 9, 30, tzinfo=datetime.UTC)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta
        mock_dt.UTC = datetime.UTC

        mock_send.kiq = AsyncMock()
        mock_send.schedule_by_time = AsyncMock()
        mock_followup.schedule_by_time = AsyncMock()
        mock_timeout.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 902)
            course = await start_course(session, 902, datetime.date(2026, 1, 1))
            # Log a dose with explicit taken_at in the mocked time range
            from bot.models.dose_log import DoseLog

            dose = DoseLog(
                course_id=course.id,
                user_id=902,
                scheduled_at=datetime.datetime(2026, 1, 1, 9, 0, tzinfo=datetime.UTC),
                taken=True,
                taken_at=datetime.datetime(2026, 1, 1, 9, 0, tzinfo=datetime.UTC),
                day=1,
                phase=1,
            )
            session.add(dose)
            await session.commit()

        await schedule_next_dose(user_id=902)
        # Next dose = 9:00 + 2h = 11:00 (future) → schedule_by_time, not kiq
        mock_send.schedule_by_time.assert_called_once()
        mock_send.kiq.assert_not_called()

    @patch("bot.tasks.datetime")
    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_dose_followup")
    @patch("bot.tasks.send_dose_reminder")
    @patch("bot.tasks.handle_dose_timeout")
    async def test_all_doses_taken_returns(
        self, mock_timeout, mock_send, mock_followup, mock_source, mock_dt, mock_session_factory
    ) -> None:
        from bot.tasks import schedule_next_dose

        fixed_now = datetime.datetime(2026, 1, 1, 20, 0, tzinfo=datetime.UTC)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta
        mock_dt.UTC = datetime.UTC

        mock_send.kiq = AsyncMock()
        mock_send.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 903)
            course = await start_course(session, 903, datetime.date(2026, 1, 1))
            # Log 6 doses (phase 1 target)
            for i in range(6):
                await log_dose(
                    session,
                    course_id=course.id,
                    user_id=903,
                    scheduled_at=datetime.datetime(2026, 1, 1, 8 + i * 2, 0, tzinfo=datetime.UTC),
                    day=1,
                    phase=1,
                )
            await session.commit()

        await schedule_next_dose(user_id=903)
        # All 6 doses taken → no more reminders
        mock_send.kiq.assert_not_called()
        mock_send.schedule_by_time.assert_not_called()


class TestHandleDoseTimeout:
    @patch("bot.tasks.schedule_next_dose")
    async def test_stale_timeout_skips(self, mock_snd, mock_session_factory) -> None:
        from bot.tasks import handle_dose_timeout

        mock_snd.kiq = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 910)
            course = await start_course(session, 910, datetime.date.today())
            # Log 1 dose → taken=1
            await log_dose(
                session,
                course_id=course.id,
                user_id=910,
                scheduled_at=datetime.datetime.now(datetime.UTC),
                day=1,
                phase=1,
            )
            await session.commit()

        await handle_dose_timeout(user_id=910, expected_taken=1)
        # taken (1) >= expected (1) → stale, skip
        mock_snd.kiq.assert_not_called()

    @patch("bot.tasks.schedule_next_dose")
    async def test_missed_dose_advances_chain(self, mock_snd, mock_session_factory) -> None:
        from bot.tasks import handle_dose_timeout

        mock_snd.kiq = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 911)
            await start_course(session, 911, datetime.date.today())
            await session.commit()

        await handle_dose_timeout(user_id=911, expected_taken=1)
        # taken (0) < expected (1) → missed, advance chain
        mock_snd.kiq.assert_called_once_with(911)

    @patch("bot.tasks.schedule_next_dose")
    async def test_no_course_returns(self, mock_snd, mock_session_factory) -> None:
        from bot.tasks import handle_dose_timeout

        mock_snd.kiq = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 912)
            await session.commit()

        await handle_dose_timeout(user_id=912, expected_taken=1)
        mock_snd.kiq.assert_not_called()


class TestAutoStartDoses:
    @patch("bot.tasks.schedule_next_dose")
    async def test_starts_chain_when_no_doses(self, mock_snd, mock_session_factory) -> None:
        from bot.tasks import auto_start_doses

        mock_snd.kiq = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 920)
            await start_course(session, 920, datetime.date.today())
            await session.commit()

        await auto_start_doses(user_id=920)
        mock_snd.kiq.assert_called_once_with(920)

    @patch("bot.tasks.schedule_next_dose")
    async def test_skips_when_doses_taken(self, mock_snd, mock_session_factory) -> None:
        from bot.tasks import auto_start_doses

        mock_snd.kiq = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 921)
            course = await start_course(session, 921, datetime.date.today())
            await log_dose(
                session,
                course_id=course.id,
                user_id=921,
                scheduled_at=datetime.datetime.now(datetime.UTC),
                day=1,
                phase=1,
            )
            await session.commit()

        await auto_start_doses(user_id=921)
        mock_snd.kiq.assert_not_called()

    @patch("bot.tasks.schedule_next_dose")
    async def test_no_course_returns(self, mock_snd, mock_session_factory) -> None:
        from bot.tasks import auto_start_doses

        mock_snd.kiq = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 922)
            await session.commit()

        await auto_start_doses(user_id=922)
        mock_snd.kiq.assert_not_called()
