"""Tests for new features: SOS, savings, health, achievements, relapse, mood."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.course import (
    ACHIEVEMENT_DEFS,
    check_and_grant_achievements,
    get_craving_count,
    get_mood_history,
    get_or_create_user,
    get_relapse_stats,
    get_smoking_profile,
    get_user_achievements,
    grant_achievement,
    log_craving,
    log_dose,
    log_mood,
    log_relapse,
    save_smoking_profile,
    start_course,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


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


def _make_message(user_id: int = 123, text: str = "") -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def _make_state() -> MagicMock:
    state = MagicMock()
    _data: dict = {}
    state.set_state = AsyncMock()
    state.update_data = AsyncMock(side_effect=lambda **kw: _data.update(kw))
    state.get_data = AsyncMock(return_value=_data)
    state.clear = AsyncMock()
    return state


# ── Smoking Profile Service ─────────────────────────────────────────────────


class TestSmokingProfile:
    async def test_save_and_get_profile(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        profile = await save_smoking_profile(db_session, 12345, 20, 150.0)
        assert profile.cigarettes_per_day == 20
        assert profile.pack_price == 150.0
        assert profile.cigarettes_in_pack == 20

        fetched = await get_smoking_profile(db_session, 12345)
        assert fetched is not None
        assert fetched.cigarettes_per_day == 20

    async def test_update_existing_profile(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await save_smoking_profile(db_session, 12345, 20, 150.0)
        updated = await save_smoking_profile(db_session, 12345, 10, 200.0)
        assert updated.cigarettes_per_day == 10
        assert updated.pack_price == 200.0

    async def test_no_profile(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        assert await get_smoking_profile(db_session, 12345) is None


# ── Craving Log Service ─────────────────────────────────────────────────────


class TestCravingLog:
    async def test_log_and_count(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await log_craving(db_session, 12345)
        await log_craving(db_session, 12345)
        count = await get_craving_count(db_session, 12345)
        assert count == 2

    async def test_empty_count(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        assert await get_craving_count(db_session, 12345) == 0


# ── Mood Log Service ────────────────────────────────────────────────────────


class TestMoodLog:
    async def test_log_mood(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        entry = await log_mood(db_session, 12345, "good")
        assert entry.mood == "good"

    async def test_mood_history(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await log_mood(db_session, 12345, "good")
        await log_mood(db_session, 12345, "neutral")
        await log_mood(db_session, 12345, "bad")

        history = await get_mood_history(db_session, 12345, limit=2)
        assert len(history) == 2

    async def test_empty_history(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        history = await get_mood_history(db_session, 12345)
        assert history == []


# ── Relapse Log Service ─────────────────────────────────────────────────────


class TestRelapseLog:
    async def test_log_relapse(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        entry = await log_relapse(db_session, 12345, 3)
        assert entry.cigarettes == 3

    async def test_relapse_stats(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await log_relapse(db_session, 12345, 2)
        await log_relapse(db_session, 12345, 5)
        stats = await get_relapse_stats(db_session, 12345)
        assert stats["count"] == 2
        assert stats["total_cigarettes"] == 7

    async def test_empty_stats(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        stats = await get_relapse_stats(db_session, 12345)
        assert stats["count"] == 0
        assert stats["total_cigarettes"] == 0


# ── Achievements Service ────────────────────────────────────────────────────


class TestAchievements:
    async def test_grant_achievement(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        a = await grant_achievement(db_session, 12345, "first_dose")
        assert a is not None
        assert a.key == "first_dose"

    async def test_no_duplicate_achievement(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        a1 = await grant_achievement(db_session, 12345, "first_dose")
        a2 = await grant_achievement(db_session, 12345, "first_dose")
        assert a1 is not None
        assert a2 is None

    async def test_get_user_achievements(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await grant_achievement(db_session, 12345, "first_dose")
        await grant_achievement(db_session, 12345, "doses_10")
        earned = await get_user_achievements(db_session, 12345)
        assert len(earned) == 2
        keys = {a.key for a in earned}
        assert "first_dose" in keys
        assert "doses_10" in keys

    async def test_check_and_grant_first_dose(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))
        await log_dose(
            db_session,
            course_id=course.id,
            user_id=12345,
            scheduled_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            day=1,
            phase=1,
        )

        newly = await check_and_grant_achievements(db_session, 12345)
        assert "first_dose" in newly

        # Second check should not re-grant
        newly2 = await check_and_grant_achievements(db_session, 12345)
        assert "first_dose" not in newly2

    async def test_achievement_defs_complete(self) -> None:
        assert len(ACHIEVEMENT_DEFS) > 0
        for key, (title, desc) in ACHIEVEMENT_DEFS.items():
            assert isinstance(title, str)
            assert isinstance(desc, str)
            assert len(title) > 0
            assert len(desc) > 0


# ── Text Templates ──────────────────────────────────────────────────────────


class TestNewTexts:
    def test_sos_craving_text(self) -> None:
        from bot.utils.texts import sos_craving_text

        text = sos_craving_text(3, 5)
        assert "Тяга" in text or "тяга" in text
        assert "3" in text
        assert "5" in text

    def test_sos_craving_text_no_days(self) -> None:
        from bot.utils.texts import sos_craving_text

        text = sos_craving_text(0, 0)
        assert "Тяга" in text or "тяга" in text

    def test_health_timeline_text(self) -> None:
        from bot.utils.texts import health_timeline_text

        text = health_timeline_text(72)
        assert "✅" in text
        assert "⏳" in text

    def test_health_timeline_text_zero(self) -> None:
        from bot.utils.texts import health_timeline_text

        text = health_timeline_text(0)
        assert "Восстановление" in text

    def test_savings_text(self) -> None:
        from bot.utils.texts import savings_text

        text = savings_text(10, 200, 1500.0, ["☕ 300 чашек кофе"])
        assert "1500" in text
        assert "200" in text
        assert "кофе" in text

    def test_achievements_text_empty(self) -> None:
        from bot.utils.texts import achievements_text

        text = achievements_text([], 11)
        assert "0/11" in text
        assert "Пока нет" in text

    def test_achievements_text_with_earned(self) -> None:
        from bot.utils.texts import achievements_text

        earned = [("first_dose", "💊 Первая таблетка", "Принял первую таблетку Табекс")]
        text = achievements_text(earned, 11)
        assert "1/11" in text
        assert "Первая таблетка" in text

    def test_relapse_logged_text(self) -> None:
        from bot.utils.texts import relapse_logged_text

        text = relapse_logged_text(2, 5, 20)
        assert "2" in text
        assert "5" in text
        assert "20" in text

    def test_relapse_logged_text_no_profile(self) -> None:
        from bot.utils.texts import relapse_logged_text

        text = relapse_logged_text(1, 3, None)
        assert "1" in text
        assert "3" in text

    def test_morning_checkin_text(self) -> None:
        from bot.utils.texts import morning_checkin_text

        text = morning_checkin_text(5)
        assert "5/25" in text
        assert "утро" in text.lower()

    def test_mood_logged_text(self) -> None:
        from bot.utils.texts import mood_logged_text

        assert "Отлично" in mood_logged_text("good")
        assert "Нормально" in mood_logged_text("neutral") or "Нормально" in mood_logged_text(
            "neutral"
        )
        assert "SOS" in mood_logged_text("bad") or "тяжёлые" in mood_logged_text("bad")

    def test_mood_history_text(self) -> None:
        from bot.utils.texts import mood_history_text

        text = mood_history_text([("01.04", "good"), ("02.04", "bad")])
        assert "😊" in text
        assert "😟" in text

    def test_mood_history_text_empty(self) -> None:
        from bot.utils.texts import mood_history_text

        text = mood_history_text([])
        assert "Пока нет" in text

    def test_new_achievement_text(self) -> None:
        from bot.utils.texts import new_achievement_text

        text = new_achievement_text("💊 Первая таблетка", "Принял первую таблетку")
        assert "Новое достижение" in text
        assert "Первая таблетка" in text

    def test_ask_cigarettes_per_day(self) -> None:
        from bot.utils.texts import ask_cigarettes_per_day_text

        text = ask_cigarettes_per_day_text()
        assert "сигарет" in text.lower()

    def test_ask_pack_price(self) -> None:
        from bot.utils.texts import ask_pack_price_text

        text = ask_pack_price_text()
        assert "пачка" in text.lower() or "стоит" in text.lower()


# ── Keyboard Tests ──────────────────────────────────────────────────────────


class TestNewKeyboards:
    def test_mood_keyboard(self) -> None:
        from bot.keyboards.inline import mood_keyboard

        kb = mood_keyboard()
        assert len(kb.inline_keyboard) == 1
        buttons = kb.inline_keyboard[0]
        assert len(buttons) == 3
        texts = [b.text for b in buttons]
        assert any("Хорошо" in t for t in texts)
        assert any("Нормально" in t for t in texts)
        assert any("Плохо" in t for t in texts)

    def test_mood_callback(self) -> None:
        from bot.keyboards.inline import MoodCallback

        cb = MoodCallback(value="good")
        packed = cb.pack()
        unpacked = MoodCallback.unpack(packed)
        assert unpacked.value == "good"

    def test_main_menu_has_sos_button(self) -> None:
        from bot.keyboards.inline import main_menu_keyboard

        kb = main_menu_keyboard(has_course=True)
        all_texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("закурить" in t.lower() for t in all_texts)

    def test_main_menu_has_relapse_button(self) -> None:
        from bot.keyboards.inline import main_menu_keyboard

        kb = main_menu_keyboard(has_course=True)
        all_texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("закурил" in t.lower() for t in all_texts)

    def test_main_menu_no_course_no_sos(self) -> None:
        from bot.keyboards.inline import main_menu_keyboard

        kb = main_menu_keyboard(has_course=False)
        all_texts = [b.text for row in kb.inline_keyboard for b in row]
        assert not any("закурить" in t.lower() for t in all_texts)


# ── Handler Tests ───────────────────────────────────────────────────────────


class TestNewMenuHandlers:
    @pytest.fixture(autouse=True)
    def _patch_taskiq(self):
        with (
            patch("bot.handlers.course.schedule_source") as mock_ss,
            patch("bot.handlers.course.schedule_daily_doses") as mock_sdd,
            patch("bot.handlers.course.schedule_next_day") as mock_snd,
        ):
            mock_ss.startup = AsyncMock()
            mock_sdd.kiq = AsyncMock()
            mock_snd.kiq = AsyncMock()
            yield

    async def test_sos_no_course(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_sos

        cb = _make_callback(user_id=900)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 900)
            await session.commit()

        await on_menu_sos(cb)
        cb.answer.assert_called()
        assert "нет активного" in cb.answer.call_args[0][0].lower()

    async def test_sos_with_course(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_sos

        cb = _make_callback(user_id=901)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 901)
            await start_course(session, 901, datetime.date.today())
            await session.commit()

        await on_menu_sos(cb)
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Тяга" in text or "тяга" in text

    async def test_savings_no_profile(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_savings

        cb = _make_callback(user_id=902)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 902)
            await start_course(session, 902, datetime.date.today())
            await session.commit()

        await on_menu_savings(cb)
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "профиль" in text.lower()

    async def test_savings_with_profile(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_savings

        cb = _make_callback(user_id=903)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 903)
            # Start course 10 days ago (past quit day)
            await start_course(
                session,
                903,
                datetime.date.today() - datetime.timedelta(days=9),
            )
            await save_smoking_profile(session, 903, 20, 150.0)
            await session.commit()

        await on_menu_savings(cb)
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Экономия" in text or "экономил" in text.lower() or "Сэкономлено" in text

    async def test_health_timeline(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_health

        cb = _make_callback(user_id=904)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 904)
            await start_course(session, 904, datetime.date.today())
            await session.commit()

        await on_menu_health(cb)
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Восстановление" in text

    async def test_achievements_empty(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_achievements

        cb = _make_callback(user_id=905)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 905)
            await session.commit()

        await on_menu_achievements(cb)
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Достижения" in text

    async def test_relapse_flow(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_relapse, on_relapse_count

        # Step 1: click relapse button
        cb = _make_callback(user_id=906)
        state = _make_state()
        async with mock_session_factory() as session:
            await get_or_create_user(session, 906)
            await start_course(session, 906, datetime.date.today())
            await session.commit()

        await on_menu_relapse(cb, state)
        state.set_state.assert_called_once()

        # Step 2: send cigarette count
        msg = _make_message(user_id=906, text="3")
        await on_relapse_count(msg, state)
        state.clear.assert_called_once()
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Записано" in text

    async def test_relapse_invalid_count(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_relapse_count

        msg = _make_message(user_id=907, text="abc")
        state = _make_state()
        await on_relapse_count(msg, state)
        msg.answer.assert_called_once()
        assert "число" in msg.answer.call_args[0][0].lower()
        state.clear.assert_not_called()

    async def test_mood_history_handler(self, mock_session_factory) -> None:
        from bot.handlers.menu import on_menu_mood_history

        cb = _make_callback(user_id=908)
        async with mock_session_factory() as session:
            await get_or_create_user(session, 908)
            await log_mood(session, 908, "good")
            await session.commit()

        await on_menu_mood_history(cb)
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Настроение" in text


# ── Mood Handler ─────────────────────────────────────────────────────────────


class TestMoodHandler:
    async def test_on_mood_selected(self, mock_session_factory) -> None:
        from bot.handlers.mood import on_mood_selected
        from bot.keyboards.inline import MoodCallback

        cb = _make_callback(user_id=910)
        cb_data = MoodCallback(value="good")

        async with mock_session_factory() as session:
            await get_or_create_user(session, 910)
            await session.commit()

        await on_mood_selected(cb, cb_data)
        cb.message.edit_text.assert_called_once()
        cb.answer.assert_called_once()


# ── Settings Smoking Profile Handlers ────────────────────────────────────────


class TestSmokingProfileHandlers:
    async def test_on_change_smoking_profile(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_change_smoking_profile

        cb = _make_callback(user_id=920)
        state = _make_state()
        await on_change_smoking_profile(cb, state)
        cb.message.answer.assert_called_once()
        state.set_state.assert_called_once()

    async def test_on_cigarettes_per_day_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_cigarettes_per_day

        msg = _make_message(user_id=921, text="20")
        state = _make_state()
        await on_cigarettes_per_day(msg, state)
        state.update_data.assert_called_once_with(cigarettes_per_day=20)
        msg.answer.assert_called_once()

    async def test_on_cigarettes_per_day_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_cigarettes_per_day

        msg = _make_message(user_id=922, text="abc")
        state = _make_state()
        await on_cigarettes_per_day(msg, state)
        msg.answer.assert_called_once()
        assert "число" in msg.answer.call_args[0][0].lower()

    async def test_on_pack_price_valid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_pack_price

        msg = _make_message(user_id=923, text="150")
        state = _make_state()
        state_data = {"cigarettes_per_day": 20}
        state.get_data = AsyncMock(return_value=state_data)

        async with mock_session_factory() as session:
            await get_or_create_user(session, 923)
            await session.commit()

        await on_pack_price(msg, state)
        state.clear.assert_called_once()
        msg.answer.assert_called_once()

    async def test_on_pack_price_invalid(self, mock_session_factory) -> None:
        from bot.handlers.settings import on_pack_price

        msg = _make_message(user_id=924, text="abc")
        state = _make_state()
        await on_pack_price(msg, state)
        msg.answer.assert_called_once()
        assert (
            "число" in msg.answer.call_args[0][0].lower()
            or "цену" in msg.answer.call_args[0][0].lower()
        )


# ── Onboarding Smoking Profile ──────────────────────────────────────────────


class TestOnboardingSmokingProfile:
    async def test_onboard_cigarettes_valid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_onboard_cigarettes

        msg = _make_message(user_id=930, text="15")
        state = _make_state()
        await on_onboard_cigarettes(msg, state)
        state.update_data.assert_called_once_with(cigarettes_per_day=15)
        msg.answer.assert_called_once()
        state.set_state.assert_called_once()

    async def test_onboard_cigarettes_invalid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_onboard_cigarettes

        msg = _make_message(user_id=931, text="abc")
        state = _make_state()
        await on_onboard_cigarettes(msg, state)
        msg.answer.assert_called_once()
        state.update_data.assert_not_called()

    async def test_onboard_pack_price_valid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_onboard_pack_price

        msg = _make_message(user_id=932, text="150")
        state = _make_state()
        state_data = {"cigarettes_per_day": 20}
        state.get_data = AsyncMock(return_value=state_data)

        async with mock_session_factory() as session:
            await get_or_create_user(session, 932)
            await session.commit()

        await on_onboard_pack_price(msg, state)
        state.clear.assert_called_once()
        msg.answer.assert_called_once()

    async def test_onboard_pack_price_invalid(self, mock_session_factory) -> None:
        from bot.handlers.start import on_onboard_pack_price

        msg = _make_message(user_id=933, text="abc")
        state = _make_state()
        await on_onboard_pack_price(msg, state)
        msg.answer.assert_called_once()
        state.clear.assert_not_called()


# ── Morning Check-in Task ───────────────────────────────────────────────────


class TestMorningCheckin:
    @patch("bot.tasks.Bot")
    async def test_sends_checkin(self, mock_bot_cls, mock_session_factory) -> None:
        from bot.tasks import send_morning_checkin

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.session = MagicMock()
        bot.session.close = AsyncMock()
        mock_bot_cls.return_value = bot

        async with mock_session_factory() as session:
            await get_or_create_user(session, 950)
            await start_course(session, 950, datetime.date.today())
            await session.commit()

        await send_morning_checkin(user_id=950)
        bot.send_message.assert_called_once()
        text = bot.send_message.call_args[0][1]
        assert "утро" in text.lower()

    @patch("bot.tasks.Bot")
    async def test_no_course_returns(self, mock_bot_cls, mock_session_factory) -> None:
        from bot.tasks import send_morning_checkin

        async with mock_session_factory() as session:
            await get_or_create_user(session, 951)
            await session.commit()

        await send_morning_checkin(user_id=951)
        mock_bot_cls.return_value.send_message.assert_not_called()
