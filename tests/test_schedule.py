"""Tests for the schedule calculator — the core protocol logic."""

import datetime

import pytest

from bot.services.schedule import (
    COURSE_DAYS,
    PHASES,
    QUIT_DAY,
    DoseSlot,
    PhaseInfo,
    calculate_dose_times,
    calculate_remaining_doses_today,
    get_course_day,
    get_phase,
    get_progress,
    is_first_day_of_phase,
    is_quit_day,
)


class TestGetPhase:
    """Verify phase boundaries match the Tabex protocol exactly."""

    @pytest.mark.parametrize(
        ("day", "expected_phase", "expected_interval", "expected_tablets", "expected_min_tablets"),
        [
            # Phase 1: days 1–3, every 2h, 6 tablets
            (1, 1, 120, 6, 6),
            (2, 1, 120, 6, 6),
            (3, 1, 120, 6, 6),
            # Phase 2: days 4–12, every 2.5h, 5 tablets
            (4, 2, 150, 5, 5),
            (8, 2, 150, 5, 5),
            (12, 2, 150, 5, 5),
            # Phase 3: days 13–16, every 3h, 4 tablets
            (13, 3, 180, 4, 4),
            (16, 3, 180, 4, 4),
            # Phase 4: days 17–20, every 5h, 3 tablets
            (17, 4, 300, 3, 3),
            (20, 4, 300, 3, 3),
            # Phase 5: days 21–25, every 5h, 1–2 tablets
            (21, 5, 300, 2, 1),
            (25, 5, 300, 2, 1),
        ],
    )
    def test_correct_phase_for_each_day(
        self,
        day: int,
        expected_phase: int,
        expected_interval: int,
        expected_tablets: int,
        expected_min_tablets: int,
    ) -> None:
        phase = get_phase(day)
        assert phase.phase == expected_phase
        assert phase.interval_minutes == expected_interval
        assert phase.target_tablets == expected_tablets
        assert phase.min_tablets == expected_min_tablets

    def test_day_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="outside the 25-day course"):
            get_phase(0)

    def test_day_26_raises(self) -> None:
        with pytest.raises(ValueError, match="outside the 25-day course"):
            get_phase(26)

    def test_negative_day_raises(self) -> None:
        with pytest.raises(ValueError):
            get_phase(-1)

    def test_returns_phase_info_dataclass(self) -> None:
        info = get_phase(1)
        assert isinstance(info, PhaseInfo)
        assert info.start_day == 1
        assert info.end_day == 3
        assert info.min_tablets == 6

    def test_phase5_target_display(self) -> None:
        info = get_phase(21)
        assert info.target_display == "1–2"

    def test_phase1_target_display(self) -> None:
        info = get_phase(1)
        assert info.target_display == "6"


class TestGetCourseDay:
    def test_first_day(self) -> None:
        assert get_course_day(datetime.date(2026, 1, 1), datetime.date(2026, 1, 1)) == 1

    def test_day_5(self) -> None:
        assert get_course_day(datetime.date(2026, 1, 1), datetime.date(2026, 1, 5)) == 5

    def test_day_25(self) -> None:
        assert get_course_day(datetime.date(2026, 1, 1), datetime.date(2026, 1, 25)) == 25

    def test_before_start(self) -> None:
        assert get_course_day(datetime.date(2026, 1, 5), datetime.date(2026, 1, 3)) == -1


class TestIsQuitDay:
    def test_before_quit_day(self) -> None:
        assert is_quit_day(4) is False

    def test_quit_day_exact(self) -> None:
        assert is_quit_day(5) is True

    def test_after_quit_day(self) -> None:
        assert is_quit_day(10) is True

    def test_quit_day_constant(self) -> None:
        assert QUIT_DAY == 5


class TestCalculateDoseTimes:
    """Verify dose counts match protocol for standard 08:00–22:00 waking window."""

    def test_phase1_gives_6_doses(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(1, wake_time, sleep_time, course_start_date, timezone)
        assert len(slots) == 6
        assert all(s.phase == 1 for s in slots)
        assert all(s.day == 1 for s in slots)

    def test_phase2_gives_5_doses(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(5, wake_time, sleep_time, course_start_date, timezone)
        assert len(slots) == 5

    def test_phase3_gives_4_doses(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(14, wake_time, sleep_time, course_start_date, timezone)
        assert len(slots) == 4

    def test_phase4_gives_3_doses(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(18, wake_time, sleep_time, course_start_date, timezone)
        assert len(slots) == 3

    def test_phase5_gives_2_doses(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(22, wake_time, sleep_time, course_start_date, timezone)
        assert len(slots) == 2

    def test_first_dose_at_wake_time(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(1, wake_time, sleep_time, course_start_date, timezone)
        assert slots[0].time.hour == 8
        assert slots[0].time.minute == 0

    def test_dose_interval_phase1(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(1, wake_time, sleep_time, course_start_date, timezone)
        for i in range(1, len(slots)):
            delta = slots[i].time - slots[i - 1].time
            assert delta == datetime.timedelta(hours=2)

    def test_dose_interval_phase2(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(5, wake_time, sleep_time, course_start_date, timezone)
        for i in range(1, len(slots)):
            delta = slots[i].time - slots[i - 1].time
            assert delta == datetime.timedelta(minutes=150)

    def test_no_dose_after_sleep_time(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(1, wake_time, sleep_time, course_start_date, timezone)
        for s in slots:
            assert s.time.hour < 22 or (s.time.hour == 22 and s.time.minute == 0)

    def test_returns_dose_slot_dataclass(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        slots = calculate_dose_times(1, wake_time, sleep_time, course_start_date, timezone)
        assert all(isinstance(s, DoseSlot) for s in slots)
        assert all(s.time.tzinfo is not None for s in slots)

    def test_correct_date_for_day(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        # Day 10 should have doses on Jan 10
        slots = calculate_dose_times(10, wake_time, sleep_time, course_start_date, timezone)
        for s in slots:
            assert s.time.date() == datetime.date(2026, 1, 10)

    def test_invalid_day_raises(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        with pytest.raises(ValueError):
            calculate_dose_times(0, wake_time, sleep_time, course_start_date, timezone)

    def test_short_waking_window(self, course_start_date: datetime.date, timezone: str) -> None:
        # Very short window: 10:00–14:00 (4 hours) — Phase 1 should fit only 2 doses
        slots = calculate_dose_times(
            1,
            datetime.time(10, 0),
            datetime.time(14, 0),
            course_start_date,
            timezone,
        )
        assert len(slots) == 2

    def test_overnight_sleep(self, course_start_date: datetime.date, timezone: str) -> None:
        # Sleep time crosses midnight: wake 20:00, sleep 06:00 next day
        slots = calculate_dose_times(
            1,
            datetime.time(20, 0),
            datetime.time(6, 0),
            course_start_date,
            timezone,
        )
        assert len(slots) > 0
        assert all(s.time.tzinfo is not None for s in slots)


class TestCalculateRemainingDosesToday:
    def test_returns_only_future_doses(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        # Pretend it's 12:30 on day 1 — should exclude doses at 8:00, 10:00, 12:00
        now = datetime.datetime(2026, 1, 1, 12, 30, tzinfo=tz)
        remaining = calculate_remaining_doses_today(
            1,
            wake_time,
            sleep_time,
            course_start_date,
            timezone,
            now=now,
        )
        assert all(s.time > now for s in remaining)
        assert len(remaining) == 3  # 14:00, 16:00, 18:00

    def test_all_doses_in_future(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        now = datetime.datetime(2026, 1, 1, 7, 0, tzinfo=tz)
        remaining = calculate_remaining_doses_today(
            1,
            wake_time,
            sleep_time,
            course_start_date,
            timezone,
            now=now,
        )
        assert len(remaining) == 6

    def test_no_doses_remaining(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        now = datetime.datetime(2026, 1, 1, 23, 0, tzinfo=tz)
        remaining = calculate_remaining_doses_today(
            1,
            wake_time,
            sleep_time,
            course_start_date,
            timezone,
            now=now,
        )
        assert len(remaining) == 0


class TestGetProgress:
    def test_day_1_zero_doses(self) -> None:
        stats = get_progress(1, 0)
        assert stats["day"] == 1
        assert stats["total_days"] == 25
        assert stats["phase"] == 1
        assert stats["doses_taken"] == 0
        assert stats["doses_target"] == "6"
        assert stats["percent_complete"] == 0.0

    def test_day_13_progress(self) -> None:
        stats = get_progress(13, 3)
        assert stats["phase"] == 3
        assert stats["doses_taken"] == 3
        assert stats["doses_target"] == "4"
        assert stats["percent_complete"] == 48.0

    def test_day_25_complete(self) -> None:
        stats = get_progress(25, 2)
        assert stats["percent_complete"] == 96.0
        assert stats["doses_target"] == "1–2"


class TestIsFirstDayOfPhase:
    def test_day_1_is_first_of_phase1(self) -> None:
        assert is_first_day_of_phase(1) is True

    def test_day_2_is_not_first(self) -> None:
        assert is_first_day_of_phase(2) is False

    def test_day_4_is_first_of_phase2(self) -> None:
        assert is_first_day_of_phase(4) is True

    def test_day_13_is_first_of_phase3(self) -> None:
        assert is_first_day_of_phase(13) is True

    def test_day_17_is_first_of_phase4(self) -> None:
        assert is_first_day_of_phase(17) is True

    def test_day_21_is_first_of_phase5(self) -> None:
        assert is_first_day_of_phase(21) is True

    def test_day_12_is_not_first(self) -> None:
        assert is_first_day_of_phase(12) is False

    def test_day_25_is_not_first(self) -> None:
        assert is_first_day_of_phase(25) is False


class TestProtocolConstants:
    def test_course_length(self) -> None:
        assert COURSE_DAYS == 25

    def test_quit_day(self) -> None:
        assert QUIT_DAY == 5

    def test_phases_cover_all_days(self) -> None:
        """Every day 1–25 must belong to exactly one phase."""
        covered = set()
        for start, end, _, _, _ in PHASES:
            for d in range(start, end + 1):
                assert d not in covered, f"Day {d} is in multiple phases"
                covered.add(d)
        assert covered == set(range(1, 26))

    def test_five_phases(self) -> None:
        assert len(PHASES) == 5
