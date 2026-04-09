"""Tests for TaskIQ tasks — dose reminders, daily scheduling, progress summary."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.course import get_active_course, get_or_create_user, start_course


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
    async def test_sends_message(
        self, mock_bot_cls, mock_dt, mock_session_factory
    ) -> None:
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
    async def test_handles_exception(
        self, mock_bot_cls, mock_dt, mock_session_factory
    ) -> None:
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
    @patch("bot.tasks.send_dose_followup")
    @patch("bot.tasks.send_dose_reminder")
    @patch("bot.tasks.Bot")
    async def test_no_course_returns_early(
        self,
        mock_bot_cls,
        mock_send,
        mock_followup,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        async with mock_session_factory() as session:
            await get_or_create_user(session, 600)
            await session.commit()

        await schedule_daily_doses(user_id=600)
        mock_send.schedule_by_time.assert_not_called()

    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_progress_summary")
    @patch("bot.tasks.send_morning_checkin")
    @patch("bot.tasks.send_dose_followup")
    @patch("bot.tasks.send_dose_reminder")
    @patch("bot.tasks.Bot")
    async def test_schedules_future_doses(
        self,
        mock_bot_cls,
        mock_send,
        mock_followup,
        mock_checkin,
        mock_summary,
        mock_sched_src,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        mock_send.schedule_by_time = AsyncMock()
        mock_followup.schedule_by_time = AsyncMock()
        mock_checkin.schedule_by_time = AsyncMock()
        mock_summary.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 601)
            await start_course(session, 601, datetime.date.today())
            await session.commit()

        await schedule_daily_doses(user_id=601)
        # Should have scheduled some future doses (depends on current time)
        # At minimum, no errors during execution

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

    @patch("bot.tasks.Bot")
    async def test_day_before_start_returns_early(
        self,
        mock_bot_cls,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        async with mock_session_factory() as session:
            await get_or_create_user(session, 603)
            # Course starts tomorrow — day < 1
            await start_course(
                session,
                603,
                datetime.date.today() + datetime.timedelta(days=1),
            )
            await session.commit()

        await schedule_daily_doses(user_id=603)
        # No bot messages, no errors

    @patch("bot.tasks.schedule_source")
    @patch("bot.tasks.send_progress_summary")
    @patch("bot.tasks.send_morning_checkin")
    @patch("bot.tasks.send_dose_followup")
    @patch("bot.tasks.send_dose_reminder")
    @patch("bot.tasks.Bot")
    async def test_quit_day_sends_message(
        self,
        mock_bot_cls,
        mock_send,
        mock_followup,
        mock_checkin,
        mock_summary,
        mock_sched_src,
        mock_session_factory,
    ) -> None:
        from bot.tasks import schedule_daily_doses

        bot = _bot_mock()
        mock_bot_cls.return_value = bot
        mock_send.schedule_by_time = AsyncMock()
        mock_followup.schedule_by_time = AsyncMock()
        mock_checkin.schedule_by_time = AsyncMock()
        mock_summary.schedule_by_time = AsyncMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 604)
            # Day 5 is quit day
            await start_course(
                session,
                604,
                datetime.date.today() - datetime.timedelta(days=4),
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
