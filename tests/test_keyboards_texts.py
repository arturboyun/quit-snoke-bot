"""Tests for keyboards, text templates, and throttle middleware."""

from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Update

from bot.keyboards.inline import (
    POPULAR_TIMEZONES,
    CourseCallback,
    DoseCallback,
    MenuCallback,
    SettingsCallback,
    confirm_cancel_keyboard,
    confirm_start_keyboard,
    dose_taken_keyboard,
    main_menu_keyboard,
    settings_keyboard,
    timezone_keyboard,
)
from bot.utils.texts import (
    already_has_course_text,
    ask_sleep_time_text,
    ask_timezone_text,
    ask_wake_time_text,
    course_cancelled_text,
    course_completed_text,
    course_started_text,
    dose_reminder_text,
    dose_taken_text,
    help_text,
    invalid_time_format_text,
    invalid_timezone_text,
    menu_text,
    no_active_course_text,
    progress_text,
    quit_day_text,
    settings_menu_text,
    settings_saved_text,
    today_schedule_text,
    welcome_text,
)


class TestCallbackData:
    def test_dose_callback_pack_unpack(self) -> None:
        cb = DoseCallback(action="taken", course_id=42, day=3, phase=1)
        packed = cb.pack()
        unpacked = DoseCallback.unpack(packed)
        assert unpacked.action == "taken"
        assert unpacked.course_id == 42
        assert unpacked.day == 3
        assert unpacked.phase == 1

    def test_course_callback(self) -> None:
        cb = CourseCallback(action="confirm_start")
        packed = cb.pack()
        unpacked = CourseCallback.unpack(packed)
        assert unpacked.action == "confirm_start"

    def test_settings_callback(self) -> None:
        cb = SettingsCallback(action="timezone")
        packed = cb.pack()
        unpacked = SettingsCallback.unpack(packed)
        assert unpacked.action == "timezone"


class TestKeyboards:
    def test_dose_taken_keyboard_has_button(self) -> None:
        kb = dose_taken_keyboard(course_id=1, day=3, phase=1)
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 1
        button = kb.inline_keyboard[0][0]
        assert "Принял" in button.text
        assert button.callback_data is not None

    def test_confirm_start_keyboard(self) -> None:
        kb = confirm_start_keyboard()
        buttons = kb.inline_keyboard[0]
        assert len(buttons) == 2
        texts = [b.text for b in buttons]
        assert any("Начать" in t for t in texts)
        assert any("Отмена" in t for t in texts)

    def test_confirm_cancel_keyboard(self) -> None:
        kb = confirm_cancel_keyboard()
        buttons = kb.inline_keyboard[0]
        assert len(buttons) == 2

    def test_timezone_keyboard_contains_kyiv(self) -> None:
        kb = timezone_keyboard()
        all_texts = [b.text for row in kb.inline_keyboard for b in row]
        assert "Europe/Kyiv" in all_texts

    def test_timezone_keyboard_all_popular(self) -> None:
        kb = timezone_keyboard()
        all_texts = [b.text for row in kb.inline_keyboard for b in row]
        for tz in POPULAR_TIMEZONES:
            assert tz in all_texts

    def test_settings_keyboard_five_rows(self) -> None:
        kb = settings_keyboard()
        assert len(kb.inline_keyboard) == 5  # tz, wake, sleep, smoking_profile, back


class TestTexts:
    def test_welcome_text_not_empty(self) -> None:
        text = welcome_text()
        assert len(text) > 0
        assert "Табекс" in text

    def test_course_started_includes_date(self) -> None:
        text = course_started_text("2026-04-01")
        assert "2026-04-01" in text
        assert "25" in text

    def test_dose_reminder_includes_day_info(self) -> None:
        text = dose_reminder_text(day=3, phase=1, target=6)
        assert "3/25" in text
        assert "6" in text

    def test_dose_taken_shows_count(self) -> None:
        text = dose_taken_text(taken_today=3, target=6)
        assert "3/6" in text

    def test_quit_day_text_emphasis(self) -> None:
        text = quit_day_text()
        assert "ДЕНЬ 5" in text
        assert "ОТКАЗ" in text

    def test_progress_text_bar(self) -> None:
        stats = {
            "day": 13,
            "total_days": 25,
            "phase": 3,
            "doses_taken": 2,
            "doses_target": 4,
            "percent_complete": 48.0,
        }
        text = progress_text(stats)
        assert "13/25" in text
        assert "2/4" in text
        assert "48.0%" in text
        assert "▓" in text

    def test_course_completed_text(self) -> None:
        text = course_completed_text()
        assert "25" in text
        assert "Поздравляю" in text

    def test_today_schedule_shows_times(self) -> None:
        text = today_schedule_text(day=1, phase=1, times=["08:00", "10:00"], target=6)
        assert "08:00" in text
        assert "10:00" in text
        assert "1/25" in text

    def test_settings_menu_text(self) -> None:
        text = settings_menu_text("Europe/Moscow", "08:00", "22:00")
        assert "Europe/Moscow" in text
        assert "08:00" in text
        assert "22:00" in text

    def test_help_text_lists_commands(self) -> None:
        text = help_text()
        assert "/start" in text

    def test_all_text_functions_return_strings(self) -> None:
        """Ensure all text functions produce non-empty strings."""
        results = [
            welcome_text(),
            ask_timezone_text(),
            ask_wake_time_text(),
            ask_sleep_time_text(),
            settings_saved_text(),
            course_started_text("2026-01-01"),
            already_has_course_text(),
            no_active_course_text(),
            dose_reminder_text(1, 1, 6),
            dose_taken_text(1, 6),
            quit_day_text(),
            course_completed_text(),
            course_cancelled_text(),
            invalid_time_format_text(),
            invalid_timezone_text(),
            help_text(),
        ]
        for r in results:
            assert isinstance(r, str)
            assert len(r) > 0


class TestThrottleMiddleware:
    async def test_allows_first_request(self) -> None:
        from bot.middlewares.throttle import ThrottleMiddleware

        mw = ThrottleMiddleware(rate_limit=1.0)
        handler = AsyncMock(return_value="ok")

        user = MagicMock()
        user.id = 1

        event = MagicMock(spec=[])  # Not an Update — should pass through
        result = await mw(handler, event, {"event_from_user": user})
        assert result == "ok"

    async def test_no_user_passes_through(self) -> None:
        from bot.middlewares.throttle import ThrottleMiddleware

        mw = ThrottleMiddleware(rate_limit=1.0)
        handler = AsyncMock(return_value="ok")

        event = MagicMock(spec=[])
        result = await mw(handler, event, {})
        assert result == "ok"

    async def test_throttles_rapid_requests(self) -> None:
        from bot.middlewares.throttle import ThrottleMiddleware

        mw = ThrottleMiddleware(rate_limit=10.0)  # very long window
        handler = AsyncMock(return_value="ok")

        user = MagicMock()
        user.id = 42

        event = MagicMock(spec=Update)
        event.update_id = 1

        # First request passes
        result1 = await mw(handler, event, {"event_from_user": user})
        assert result1 == "ok"

        # Second rapid request is throttled
        result2 = await mw(handler, event, {"event_from_user": user})
        assert result2 is None

    async def test_allows_after_rate_limit(self) -> None:
        from bot.middlewares.throttle import ThrottleMiddleware

        mw = ThrottleMiddleware(rate_limit=0.0)  # no throttle
        handler = AsyncMock(return_value="ok")

        user = MagicMock()
        user.id = 99

        event = MagicMock(spec=Update)
        event.update_id = 1

        result1 = await mw(handler, event, {"event_from_user": user})
        assert result1 == "ok"

        result2 = await mw(handler, event, {"event_from_user": user})
        assert result2 == "ok"

    async def test_update_without_user(self) -> None:
        from bot.middlewares.throttle import ThrottleMiddleware

        mw = ThrottleMiddleware(rate_limit=1.0)
        handler = AsyncMock(return_value="ok")

        event = MagicMock(spec=Update)
        event.update_id = 1

        result = await mw(handler, event, {"event_from_user": None})
        assert result == "ok"


class TestMenuKeyboard:
    def test_main_menu_keyboard_structure(self) -> None:
        kb = main_menu_keyboard(has_course=True)
        assert len(kb.inline_keyboard) == 7
        all_texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("таблетку" in t.lower() for t in all_texts)
        assert any("Прогресс" in t for t in all_texts)
        assert any("Расписание" in t for t in all_texts)
        assert any("Настройки" in t for t in all_texts)
        assert any("Помощь" in t for t in all_texts)
        assert any("SOS" in t or "закурить" in t.lower() for t in all_texts)
        assert any("Экономия" in t for t in all_texts)
        assert any("Здоровье" in t for t in all_texts)
        assert any("Достижения" in t for t in all_texts)
        assert any("Настроение" in t for t in all_texts)

    def test_menu_callback(self) -> None:
        cb = MenuCallback(action="take_dose")
        packed = cb.pack()
        unpacked = MenuCallback.unpack(packed)
        assert unpacked.action == "take_dose"

    def test_menu_text_not_empty(self) -> None:
        text = menu_text()
        assert len(text) > 0
        assert "Главное меню" in text
