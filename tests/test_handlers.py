"""Tests for handlers — start, course, settings, menu, progress."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.course import get_or_create_user, start_course

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_message(user_id: int = 123, text: str = "") -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def _make_callback(user_id: int = 123, data: str = "") -> MagicMock:
    cb = MagicMock()
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.message.delete = AsyncMock()
    return cb


def _make_state() -> MagicMock:
    state = MagicMock()
    _data: dict = {}
    state.set_state = AsyncMock()
    state.update_data = AsyncMock(side_effect=lambda **kw: _data.update(kw))
    state.get_data = AsyncMock(return_value=_data)
    state.clear = AsyncMock()
    return state


# ── Start Handlers ───────────────────────────────────────────────────────────


class TestStartHandlers:
    async def test_cmd_start(self, mock_session_factory) -> None:
        from bot.handlers.start import cmd_start

        msg = _make_message(user_id=111)
        state = _make_state()
        await cmd_start(msg, state)

        assert msg.answer.call_count == 2
        state.set_state.assert_called_once()

    async def test_on_timezone_button_valid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_timezone_button

        cb = _make_callback(data="tz:Europe/Kyiv")
        state = _make_state()
        await on_timezone_button(cb, state)

        state.update_data.assert_called_once_with(timezone="Europe/Kyiv")
        cb.message.edit_text.assert_called_once()
        cb.message.answer.assert_called_once()

    async def test_on_timezone_button_invalid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_timezone_button

        cb = _make_callback(data="tz:Invalid/Zone")
        state = _make_state()
        await on_timezone_button(cb, state)

        cb.answer.assert_called_once()
        state.update_data.assert_not_called()

    async def test_on_timezone_text_valid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_timezone_text

        msg = _make_message(text="Europe/Berlin")
        state = _make_state()
        await on_timezone_text(msg, state)

        state.update_data.assert_called_once_with(timezone="Europe/Berlin")
        msg.answer.assert_called_once()

    async def test_on_timezone_text_invalid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_timezone_text

        msg = _make_message(text="Not/A/Zone")
        state = _make_state()
        await on_timezone_text(msg, state)

        msg.answer.assert_called_once()
        state.update_data.assert_not_called()

    async def test_on_wake_time_valid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_wake_time

        msg = _make_message(text="07:30")
        state = _make_state()
        await on_wake_time(msg, state)

        state.update_data.assert_called_once()
        msg.answer.assert_called_once()

    async def test_on_wake_time_invalid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_wake_time

        msg = _make_message(text="not a time")
        state = _make_state()
        await on_wake_time(msg, state)

        msg.answer.assert_called_once()
        assert "ЧЧ:ММ" in msg.answer.call_args[0][0]

    async def test_on_sleep_time_valid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_sleep_time

        msg = _make_message(user_id=222, text="23:00")
        state = _make_state()
        # pre-populate state data
        state_data = {"timezone": "Europe/Kyiv", "wake_time": "08:00"}
        state.get_data = AsyncMock(return_value=state_data)

        # Create user first
        async with mock_session_factory() as session:
            await get_or_create_user(session, 222)
            await session.commit()

        await on_sleep_time(msg, state)
        # Now transitions to smoking profile step instead of clearing
        state.set_state.assert_called_once()
        msg.answer.assert_called_once()

    async def test_on_sleep_time_invalid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_sleep_time

        msg = _make_message(text="bad")
        state = _make_state()
        await on_sleep_time(msg, state)

        msg.answer.assert_called_once()
        assert "ЧЧ:ММ" in msg.answer.call_args[0][0]


# ── Course Handlers ──────────────────────────────────────────────────────────


class TestCourseHandlers:
    @pytest.fixture(autouse=True)
    def _patch_taskiq(self):
        with (
            patch("bot.handlers.course.schedule_source") as mock_ss,
            patch("bot.handlers.course.schedule_daily_doses") as mock_sdd,
            patch("bot.handlers.course.schedule_next_day") as mock_snd,
            patch("bot.handlers.course.schedule_next_dose") as mock_snd2,
        ):
            mock_ss.startup = AsyncMock()
            mock_sdd.kiq = AsyncMock()
            mock_snd.kiq = AsyncMock()
            mock_snd2.kiq = AsyncMock()
            self.mock_schedule_source = mock_ss
            self.mock_schedule_daily = mock_sdd
            self.mock_schedule_next = mock_snd
            self.mock_schedule_next_dose = mock_snd2
            yield

    async def test_start_course_no_active(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_start_course

        cb = _make_callback(user_id=300)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 300)
            await session.commit()

        await on_menu_start_course(cb)
        cb.message.edit_text.assert_called_once()
        # Now shows confirmation instead of creating immediately
        assert "Готов начать" in cb.message.edit_text.call_args[0][0]

    async def test_start_course_already_active(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_start_course

        cb = _make_callback(user_id=301)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 301)
            await start_course(session, 301, datetime.date(2026, 1, 1))
            await session.commit()

        await on_menu_start_course(cb)
        cb.message.edit_text.assert_called_once()

    async def test_cancel_course_none(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_cancel_course

        cb = _make_callback(user_id=302)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 302)
            await session.commit()

        await on_menu_cancel_course(cb)
        cb.answer.assert_called_once()
        assert "нет активного" in cb.answer.call_args[0][0].lower()

    async def test_cancel_course_active(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_cancel_course

        cb = _make_callback(user_id=303)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 303)
            await start_course(session, 303, datetime.date(2026, 1, 1))
            await session.commit()

        await on_menu_cancel_course(cb)
        cb.message.edit_text.assert_called_once()
        assert "Уверен" in cb.message.edit_text.call_args[0][0]

    async def test_on_confirm_start(self, mock_session_factory) -> None:
        from bot.handlers.course import on_confirm_start

        cb = _make_callback(user_id=304)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 304)
            await session.commit()

        await on_confirm_start(cb)
        cb.message.edit_text.assert_called_once()
        assert "Курс начат" in cb.message.edit_text.call_args[0][0]

    async def test_on_cancel_action(self, mock_session_factory) -> None:
        from bot.handlers.course import on_cancel_action

        cb = _make_callback()
        await on_cancel_action(cb)
        cb.message.edit_text.assert_called_once()
        cb.answer.assert_called_once()

    async def test_on_confirm_cancel(self, mock_session_factory) -> None:
        from bot.handlers.course import on_confirm_cancel

        cb = _make_callback(user_id=305)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 305)
            await start_course(session, 305, datetime.date(2026, 1, 1))
            await session.commit()

        await on_confirm_cancel(cb)
        cb.message.edit_text.assert_called_once()
        assert "отменён" in cb.message.edit_text.call_args[0][0].lower()

    async def test_on_dose_taken_no_course(self, mock_session_factory) -> None:
        from bot.handlers.course import on_dose_taken
        from bot.keyboards.inline import DoseCallback

        cb = _make_callback(user_id=306)
        cb_data = DoseCallback(action="taken", course_id=999, day=1, phase=1)

        async with mock_session_factory() as session:
            await get_or_create_user(session, 306)
            await session.commit()

        await on_dose_taken(cb, cb_data)
        cb.answer.assert_called_once()
        assert "не найден" in cb.answer.call_args[0][0].lower()

    @patch("bot.handlers.course.datetime")
    async def test_on_dose_taken_success(self, mock_dt, mock_session_factory) -> None:
        from bot.handlers.course import on_dose_taken
        from bot.keyboards.inline import DoseCallback

        # Fix time to midday so waking-hours check passes
        mock_dt.datetime.now.return_value = datetime.datetime(
            2026, 4, 10, 12, 0, tzinfo=datetime.UTC
        )
        mock_dt.UTC = datetime.UTC
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta

        cb = _make_callback(user_id=307)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 307)
            course = await start_course(session, 307, datetime.date.today())
            await session.commit()
            course_id = course.id

        cb_data = DoseCallback(action="taken", course_id=course_id, day=1, phase=1)
        await on_dose_taken(cb, cb_data)
        cb.message.edit_text.assert_called_once()
        assert "Отмечено" in cb.answer.call_args[0][0]


# ── Settings Handlers ────────────────────────────────────────────────────────


class TestSettingsHandlers:
    @pytest.fixture(autouse=True)
    def _patch_settings_taskiq(self):
        with (
            patch("bot.handlers.settings.schedule_source") as mock_ss,
            patch("bot.handlers.settings.schedule_daily_doses") as mock_sdd,
        ):
            mock_ss.startup = AsyncMock()
            mock_sdd.kiq = AsyncMock()
            yield

    async def test_on_change_timezone(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_change_timezone

        cb = _make_callback()
        state = _make_state()
        await on_change_timezone(cb, state)

        cb.message.answer.assert_called_once()
        state.set_state.assert_called_once()
        cb.answer.assert_called_once()

    async def test_on_change_wake(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_change_wake

        cb = _make_callback()
        state = _make_state()
        await on_change_wake(cb, state)

        cb.message.answer.assert_called_once()
        state.set_state.assert_called_once()

    async def test_on_change_sleep(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_change_sleep

        cb = _make_callback()
        state = _make_state()
        await on_change_sleep(cb, state)

        cb.message.answer.assert_called_once()
        state.set_state.assert_called_once()

    async def test_on_settings_timezone_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone

        msg = _make_message(user_id=400, text="Asia/Tokyo")
        state = _make_state()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 400)
            await session.commit()

        await on_settings_timezone(msg, state)
        state.clear.assert_called_once()
        msg.answer.assert_called_once()

    async def test_on_settings_timezone_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone

        msg = _make_message(text="Bad/Zone")
        state = _make_state()
        await on_settings_timezone(msg, state)

        msg.answer.assert_called_once()
        state.clear.assert_not_called()

    async def test_on_settings_timezone_button_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone_button

        cb = _make_callback(user_id=401, data="tz:Europe/Berlin")
        state = _make_state()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 401)
            await session.commit()

        await on_settings_timezone_button(cb, state)
        state.clear.assert_called_once()
        cb.message.edit_text.assert_called_once()

    async def test_on_settings_timezone_button_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone_button

        cb = _make_callback(data="tz:Fake/Zone")
        state = _make_state()
        await on_settings_timezone_button(cb, state)

        cb.answer.assert_called_once()
        state.clear.assert_not_called()

    async def test_on_settings_wake_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_wake

        msg = _make_message(user_id=402, text="06:30")
        state = _make_state()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 402)
            await session.commit()

        await on_settings_wake(msg, state)
        state.clear.assert_called_once()

    async def test_on_settings_wake_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_wake

        msg = _make_message(text="nope")
        state = _make_state()
        await on_settings_wake(msg, state)

        msg.answer.assert_called_once()
        state.clear.assert_not_called()

    async def test_on_settings_sleep_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_sleep

        msg = _make_message(user_id=403, text="23:30")
        state = _make_state()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 403)
            await session.commit()

        await on_settings_sleep(msg, state)
        state.clear.assert_called_once()

    async def test_on_settings_sleep_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_sleep

        msg = _make_message(text="abc")
        state = _make_state()
        await on_settings_sleep(msg, state)

        msg.answer.assert_called_once()
        state.clear.assert_not_called()


# ── Menu Handlers ────────────────────────────────────────────────────────────


class TestMenuHandlers:
    async def test_on_menu_back_shows_menu(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_back

        cb = _make_callback(user_id=420)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 420)
            await session.commit()

        await on_menu_back(cb)
        cb.message.edit_text.assert_called_once()
        cb.answer.assert_called_once()

    async def test_on_menu_back(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_back

        cb = _make_callback()
        await on_menu_back(cb)
        cb.message.edit_text.assert_called_once()
        cb.answer.assert_called_once()

    async def test_on_menu_help(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_help

        cb = _make_callback()
        await on_menu_help(cb)
        cb.message.edit_text.assert_called_once()
        cb.answer.assert_called_once()

    async def test_on_menu_take_dose_no_course(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_take_dose

        cb = _make_callback(user_id=500)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 500)
            await session.commit()

        await on_menu_take_dose(cb)
        cb.answer.assert_called_once()
        assert "Нет активного курса" in cb.answer.call_args[0][0]

    @patch("bot.handlers.menu.schedule_next_dose")
    @patch("bot.handlers.menu.datetime")
    async def test_on_menu_take_dose_success(
        self, mock_dt, mock_snd, mock_session_factory
    ) -> None:
        from bot.handlers.menu import on_menu_take_dose

        # Fix time to midday so waking-hours check passes
        mock_dt.datetime.now.return_value = datetime.datetime(
            2026, 4, 10, 12, 0, tzinfo=datetime.UTC
        )
        mock_dt.UTC = datetime.UTC
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta

        mock_snd.kiq = AsyncMock()

        cb = _make_callback(user_id=501)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 501)
            await start_course(session, 501, datetime.date.today())
            await session.commit()

        await on_menu_take_dose(cb)
        cb.message.edit_text.assert_called_once()
        assert "Отмечено" in cb.answer.call_args[0][0]
        mock_snd.kiq.assert_called_once()

    async def test_on_menu_take_dose_course_ended(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_take_dose

        cb = _make_callback(user_id=502)
        # Course started 30 days ago — day > 25
        async with mock_session_factory() as session:
            await get_or_create_user(session, 502)
            await start_course(
                session,
                502,
                datetime.date.today() - datetime.timedelta(days=30),
            )
            await session.commit()

        await on_menu_take_dose(cb)
        cb.answer.assert_called_once()
        assert "завершён" in cb.answer.call_args[0][0].lower()

    async def test_on_menu_progress_no_course(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_progress

        cb = _make_callback(user_id=503)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 503)
            await session.commit()

        await on_menu_progress(cb)
        cb.answer.assert_called_once()

    async def test_on_menu_progress_success(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_progress

        cb = _make_callback(user_id=504)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 504)
            await start_course(session, 504, datetime.date.today())
            await session.commit()

        await on_menu_progress(cb)
        cb.message.edit_text.assert_called_once()
        assert "Прогресс" in cb.message.edit_text.call_args[0][0]

    async def test_on_menu_schedule_no_course(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_schedule

        cb = _make_callback(user_id=505)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 505)
            await session.commit()

        await on_menu_schedule(cb)
        cb.answer.assert_called_once()

    async def test_on_menu_schedule_success(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_schedule

        cb = _make_callback(user_id=506)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 506)
            await start_course(session, 506, datetime.date.today())
            await session.commit()

        await on_menu_schedule(cb)
        cb.message.edit_text.assert_called_once()
        assert "Расписание" in cb.message.edit_text.call_args[0][0]

    async def test_on_menu_settings(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_settings

        cb = _make_callback(user_id=507)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 507)
            await session.commit()

        await on_menu_settings(cb)
        cb.message.edit_text.assert_called_once()
        assert "настройки" in cb.message.edit_text.call_args[0][0].lower()

    async def test_safe_edit_handles_bad_request(self, mock_session_factory) -> None:
        from aiogram.exceptions import TelegramBadRequest

        from bot.handlers.menu import _safe_edit

        cb = _make_callback()
        cb.message.edit_text = AsyncMock(
            side_effect=TelegramBadRequest(method=MagicMock(), message="message is not modified"),
        )
        # Should not raise
        await _safe_edit(cb, "test text")

    async def test_on_menu_progress_course_ended(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_progress

        cb = _make_callback(user_id=508)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 508)
            await start_course(
                session,
                508,
                datetime.date.today() - datetime.timedelta(days=30),
            )
            await session.commit()

        await on_menu_progress(cb)
        cb.answer.assert_called_once()
        assert "завершён" in cb.answer.call_args[0][0].lower()

    async def test_on_menu_schedule_course_ended(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_schedule

        cb = _make_callback(user_id=509)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 509)
            await start_course(
                session,
                509,
                datetime.date.today() - datetime.timedelta(days=30),
            )
            await session.commit()

        await on_menu_schedule(cb)
        cb.answer.assert_called_once()
        assert "завершён" in cb.answer.call_args[0][0].lower()
