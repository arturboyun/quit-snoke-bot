"""Tests for handlers — start, course, settings, menu dialog getters."""

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


def _make_dialog_manager(user_id: int = 123) -> MagicMock:
    dm = MagicMock()
    dm.start = AsyncMock()
    dm.switch_to = AsyncMock()
    dm.done = AsyncMock()
    dm.event = MagicMock()
    dm.event.from_user = MagicMock()
    dm.event.from_user.id = user_id
    dm.dialog_data = {}
    dm.middleware_data = {"state": _make_state()}
    return dm


# ── Start Handlers ───────────────────────────────────────────────────────────


class TestStartHandlers:
    async def test_cmd_start(self, mock_session_factory) -> None:
        from bot.handlers.start import cmd_start

        msg = _make_message(user_id=111)
        state = _make_state()
        dm = _make_dialog_manager(111)
        await cmd_start(msg, state, dm)

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
            patch("bot.handlers.settings.schedule_next_day") as mock_snd,
        ):
            mock_ss.startup = AsyncMock()
            mock_sdd.kiq = AsyncMock()
            mock_snd.kiq = AsyncMock()
            yield

    async def test_on_settings_timezone_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone

        msg = _make_message(user_id=400, text="Asia/Tokyo")
        state = _make_state()
        dm = _make_dialog_manager(400)

        async with mock_session_factory() as session:
            await get_or_create_user(session, 400)
            await session.commit()

        await on_settings_timezone(msg, state, dm)
        state.clear.assert_called_once()
        msg.answer.assert_called_once()
        dm.start.assert_called_once()

    async def test_on_settings_timezone_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone

        msg = _make_message(text="Bad/Zone")
        state = _make_state()
        dm = _make_dialog_manager()
        await on_settings_timezone(msg, state, dm)

        msg.answer.assert_called_once()
        state.clear.assert_not_called()

    async def test_on_settings_timezone_button_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone_button

        cb = _make_callback(user_id=401, data="tz:Europe/Berlin")
        state = _make_state()
        dm = _make_dialog_manager(401)

        async with mock_session_factory() as session:
            await get_or_create_user(session, 401)
            await session.commit()

        await on_settings_timezone_button(cb, state, dm)
        state.clear.assert_called_once()
        cb.message.edit_text.assert_called_once()
        dm.start.assert_called_once()

    async def test_on_settings_timezone_button_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_timezone_button

        cb = _make_callback(data="tz:Fake/Zone")
        state = _make_state()
        dm = _make_dialog_manager()
        await on_settings_timezone_button(cb, state, dm)

        cb.answer.assert_called_once()
        state.clear.assert_not_called()

    async def test_on_settings_wake_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_wake

        msg = _make_message(user_id=402, text="06:30")
        state = _make_state()
        dm = _make_dialog_manager(402)

        async with mock_session_factory() as session:
            await get_or_create_user(session, 402)
            await session.commit()

        await on_settings_wake(msg, state, dm)
        state.clear.assert_called_once()
        dm.start.assert_called_once()

    async def test_on_settings_wake_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_wake

        msg = _make_message(text="nope")
        state = _make_state()
        dm = _make_dialog_manager()
        await on_settings_wake(msg, state, dm)

        msg.answer.assert_called_once()
        state.clear.assert_not_called()

    async def test_on_settings_sleep_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_sleep

        msg = _make_message(user_id=403, text="23:30")
        state = _make_state()
        dm = _make_dialog_manager(403)

        async with mock_session_factory() as session:
            await get_or_create_user(session, 403)
            await session.commit()

        await on_settings_sleep(msg, state, dm)
        state.clear.assert_called_once()
        dm.start.assert_called_once()

    async def test_on_settings_sleep_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_settings_sleep

        msg = _make_message(text="abc")
        state = _make_state()
        dm = _make_dialog_manager()
        await on_settings_sleep(msg, state, dm)

        msg.answer.assert_called_once()
        state.clear.assert_not_called()


# ── Dialog Getters ───────────────────────────────────────────────────────────


class TestDialogGetters:
    async def test_main_getter_no_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import main_getter

        dm = _make_dialog_manager(user_id=420)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 420)
            await session.commit()

        result = await main_getter(dialog_manager=dm)
        assert result["has_course"] is False
        assert "Главное меню" in result["text"]

    async def test_main_getter_with_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import main_getter

        dm = _make_dialog_manager(user_id=421)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 421)
            await start_course(session, 421, datetime.date.today())
            await session.commit()

        result = await main_getter(dialog_manager=dm)
        assert result["has_course"] is True
        assert "День" in result["text"]

    async def test_progress_getter_no_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import progress_getter

        dm = _make_dialog_manager(user_id=422)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 422)
            await session.commit()

        result = await progress_getter(dialog_manager=dm)
        assert "Нет активного" in result["text"]

    async def test_progress_getter_success(self, mock_session_factory) -> None:
        from bot.dialogs.menu import progress_getter

        dm = _make_dialog_manager(user_id=423)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 423)
            await start_course(session, 423, datetime.date.today())
            await session.commit()

        result = await progress_getter(dialog_manager=dm)
        assert "Прогресс" in result["text"]

    async def test_schedule_getter_no_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import schedule_getter

        dm = _make_dialog_manager(user_id=424)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 424)
            await session.commit()

        result = await schedule_getter(dialog_manager=dm)
        assert "Нет активного" in result["text"]

    async def test_schedule_getter_success(self, mock_session_factory) -> None:
        from bot.dialogs.menu import schedule_getter

        dm = _make_dialog_manager(user_id=425)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 425)
            await start_course(session, 425, datetime.date.today())
            await session.commit()

        result = await schedule_getter(dialog_manager=dm)
        assert "Расписание" in result["text"]

    async def test_settings_getter(self, mock_session_factory) -> None:
        from bot.dialogs.menu import settings_getter

        dm = _make_dialog_manager(user_id=426)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 426)
            await session.commit()

        result = await settings_getter(dialog_manager=dm)
        assert "настройки" in result["text"].lower()

    async def test_achievements_getter(self, mock_session_factory) -> None:
        from bot.dialogs.menu import achievements_getter

        dm = _make_dialog_manager(user_id=427)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 427)
            await session.commit()

        result = await achievements_getter(dialog_manager=dm)
        assert "Достижения" in result["text"]

    async def test_history_getter_empty(self, mock_session_factory) -> None:
        from bot.dialogs.menu import history_getter

        dm = _make_dialog_manager(user_id=428)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 428)
            await session.commit()

        result = await history_getter(dialog_manager=dm)
        assert "История" in result["text"] or "пуста" in result["text"]

    async def test_mood_history_getter(self, mock_session_factory) -> None:
        from bot.dialogs.menu import mood_history_getter

        dm = _make_dialog_manager(user_id=429)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 429)
            await session.commit()

        result = await mood_history_getter(dialog_manager=dm)
        assert "Настроение" in result["text"]

    async def test_confirm_start_getter_no_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import confirm_start_getter

        dm = _make_dialog_manager(user_id=430)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 430)
            await session.commit()

        result = await confirm_start_getter(dialog_manager=dm)
        assert "Готов начать" in result["text"]

    async def test_confirm_start_getter_active(self, mock_session_factory) -> None:
        from bot.dialogs.menu import confirm_start_getter

        dm = _make_dialog_manager(user_id=431)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 431)
            await start_course(session, 431, datetime.date.today())
            await session.commit()

        result = await confirm_start_getter(dialog_manager=dm)
        assert "уже есть" in result["text"].lower()


# ── Dialog Button Callbacks ──────────────────────────────────────────────────


class TestDialogCallbacks:
    @pytest.fixture(autouse=True)
    def _patch_taskiq(self):
        with (
            patch("bot.dialogs.menu.schedule_next_dose") as mock_snd,
        ):
            mock_snd.kiq = AsyncMock()
            self.mock_schedule_next_dose = mock_snd
            yield

    async def test_on_take_dose_no_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import on_take_dose

        cb = _make_callback(user_id=500)
        dm = _make_dialog_manager(500)
        btn = MagicMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 500)
            await session.commit()

        await on_take_dose(cb, btn, dm)
        cb.answer.assert_called_once()
        assert "Нет активного курса" in cb.answer.call_args[0][0]

    @patch("bot.dialogs.menu.datetime")
    async def test_on_take_dose_success(self, mock_dt, mock_session_factory) -> None:
        from bot.dialogs.menu import on_take_dose

        mock_dt.datetime.now.return_value = datetime.datetime(
            2026, 4, 10, 12, 0, tzinfo=datetime.UTC
        )
        mock_dt.UTC = datetime.UTC
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.timedelta = datetime.timedelta

        cb = _make_callback(user_id=501)
        dm = _make_dialog_manager(501)
        btn = MagicMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 501)
            await start_course(session, 501, datetime.date.today())
            await session.commit()

        await on_take_dose(cb, btn, dm)
        cb.answer.assert_called_once()
        assert "Отмечено" in cb.answer.call_args[0][0]
        self.mock_schedule_next_dose.kiq.assert_called_once()

    async def test_on_take_dose_course_ended(self, mock_session_factory) -> None:
        from bot.dialogs.menu import on_take_dose

        cb = _make_callback(user_id=502)
        dm = _make_dialog_manager(502)
        btn = MagicMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 502)
            await start_course(
                session, 502, datetime.date.today() - datetime.timedelta(days=30),
            )
            await session.commit()

        await on_take_dose(cb, btn, dm)
        cb.answer.assert_called_once()
        assert "завершён" in cb.answer.call_args[0][0].lower()

    async def test_on_confirm_cancel_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import on_confirm_cancel_course

        cb = _make_callback(user_id=510)
        dm = _make_dialog_manager(510)
        btn = MagicMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 510)
            await start_course(session, 510, datetime.date(2026, 1, 1))
            await session.commit()

        await on_confirm_cancel_course(cb, btn, dm)
        cb.answer.assert_called_once()
        assert "отменён" in cb.answer.call_args[0][0].lower()
        dm.switch_to.assert_called_once()

    async def test_on_confirm_complete_course(self, mock_session_factory) -> None:
        from bot.dialogs.menu import on_confirm_complete_course

        cb = _make_callback(user_id=511)
        dm = _make_dialog_manager(511)
        btn = MagicMock()

        async with mock_session_factory() as session:
            await get_or_create_user(session, 511)
            await start_course(session, 511, datetime.date(2026, 1, 1))
            await session.commit()

        await on_confirm_complete_course(cb, btn, dm)
        cb.answer.assert_called_once()
        assert "завершён" in cb.answer.call_args[0][0].lower()
        dm.switch_to.assert_called_once()
