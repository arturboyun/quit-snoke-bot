"""Tests for the schedule calculator — the core protocol logic."""

import datetime

import pytest

from bot.services.schedule import (
    COURSE_DAYS,
    PHASES,
    QUIT_DAY,
    DoseSlot,
    PhaseInfo,
    build_adaptive_schedule,
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

    def test_doses_always_reach_target(
        self,
        wake_time: datetime.time,
        sleep_time: datetime.time,
        course_start_date: datetime.date,
        timezone: str,
    ) -> None:
        """All target tablets are scheduled even if they extend past sleep_time."""
        slots = calculate_dose_times(1, wake_time, sleep_time, course_start_date, timezone)
        assert len(slots) == 6  # Phase 1 target

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
        # Short window: 10:00–14:00 — all 6 doses still scheduled (extend past sleep)
        slots = calculate_dose_times(
            1,
            datetime.time(10, 0),
            datetime.time(14, 0),
            course_start_date,
            timezone,
        )
        assert len(slots) == 6

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

    def test_first_dose_at_shifts_schedule(
        self, course_start_date: datetime.date, timezone: str
    ) -> None:
        """Mid-day start: first_dose_at after wake_time shifts doses forward."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        # Wake at 08:00 but course started at 12:30 — Phase 1, 2h interval
        first_dose = datetime.datetime(2026, 1, 1, 12, 30, tzinfo=tz)
        slots = calculate_dose_times(
            1,
            datetime.time(8, 0),
            datetime.time(22, 0),
            course_start_date,
            timezone,
            first_dose_at=first_dose,
        )
        # First dose at 12:30, then 14:30, 16:30, 18:30, 20:30, 22:30 — all 6 target
        assert slots[0].time == first_dose
        assert len(slots) == 6
        for i in range(1, len(slots)):
            delta = slots[i].time - slots[i - 1].time
            assert delta == datetime.timedelta(hours=2)

    def test_first_dose_at_before_wake_uses_wake(
        self, course_start_date: datetime.date, timezone: str
    ) -> None:
        """first_dose_at before wake_time is ignored — wake_time wins."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        first_dose = datetime.datetime(2026, 1, 1, 6, 0, tzinfo=tz)
        slots = calculate_dose_times(
            1,
            datetime.time(8, 0),
            datetime.time(22, 0),
            course_start_date,
            timezone,
            first_dose_at=first_dose,
        )
        assert slots[0].time.hour == 8
        assert slots[0].time.minute == 0
        assert len(slots) == 6  # Normal full schedule

    def test_first_dose_at_day2_no_effect(
        self, course_start_date: datetime.date, timezone: str
    ) -> None:
        """On day 2, a day-1 created_at has no effect (it's in the past)."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        # Course created on day 1 at 12:30; day 2 should be normal
        first_dose = datetime.datetime(2026, 1, 1, 12, 30, tzinfo=tz)
        slots = calculate_dose_times(
            2,
            datetime.time(8, 0),
            datetime.time(22, 0),
            course_start_date,
            timezone,
            first_dose_at=first_dose,
        )
        assert slots[0].time.hour == 8
        assert slots[0].time.minute == 0
        assert len(slots) == 6

    def test_first_dose_at_late_evening_all_doses(self, course_start_date: datetime.date, timezone: str) -> None:
        """Course started very late — all target doses still scheduled past sleep."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        first_dose = datetime.datetime(2026, 1, 1, 21, 0, tzinfo=tz)
        slots = calculate_dose_times(
            1,
            datetime.time(8, 0),
            datetime.time(22, 0),
            course_start_date,
            timezone,
            first_dose_at=first_dose,
        )
        assert len(slots) == 6
        assert slots[0].time == first_dose


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


TZ = "Europe/Moscow"


class TestBuildAdaptiveSchedule:
    """Verify that build_adaptive_schedule reflects actual intake times."""

    def _tz(self) -> datetime.timezone:
        from zoneinfo import ZoneInfo

        return ZoneInfo(TZ)

    def test_no_doses_taken_projects_from_wake(self) -> None:
        """With no doses taken and no course_start_dt, slots anchor to wake_time."""
        tz = self._tz()
        now = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=tz)
        wake = datetime.time(7, 0)
        slots = build_adaptive_schedule(
            day=1,
            sleep_time=datetime.time(23, 0),
            wake_time=wake,
            timezone=TZ,
            taken_times=[],
            now=now,
        )
        assert all(not s.taken for s in slots)
        assert len(slots) == 6  # Phase 1: full 6 tablets from wake
        wake_dt = datetime.datetime(2025, 1, 1, 7, 0, tzinfo=tz)
        assert slots[0].time == wake_dt
        assert slots[1].time == wake_dt + datetime.timedelta(hours=2)

    def test_no_doses_day1_with_course_start(self) -> None:
        """Day 1 with course_start_dt anchors schedule to course start."""
        tz = self._tz()
        course_start = datetime.datetime(2025, 1, 1, 14, 0, tzinfo=tz)
        now = datetime.datetime(2025, 1, 1, 14, 5, tzinfo=tz)
        slots = build_adaptive_schedule(
            day=1,
            sleep_time=datetime.time(23, 0),
            wake_time=datetime.time(7, 0),
            timezone=TZ,
            taken_times=[],
            now=now,
            course_start_dt=course_start,
        )
        assert all(not s.taken for s in slots)
        # First slot is at course start (14:00), not now (14:05) or wake (07:00)
        assert slots[0].time == course_start
        assert slots[1].time == course_start + datetime.timedelta(hours=2)

    def test_no_doses_day2_ignores_course_start(self) -> None:
        """Day 2+ always anchors to wake_time, not course start."""
        tz = self._tz()
        course_start = datetime.datetime(2025, 1, 1, 14, 0, tzinfo=tz)
        now = datetime.datetime(2025, 1, 2, 8, 0, tzinfo=tz)
        wake = datetime.time(7, 0)
        slots = build_adaptive_schedule(
            day=2,
            sleep_time=datetime.time(23, 0),
            wake_time=wake,
            timezone=TZ,
            taken_times=[],
            now=now,
            course_start_dt=course_start,
        )
        wake_dt = datetime.datetime(2025, 1, 2, 7, 0, tzinfo=tz)
        # Full schedule from wake_time
        assert slots[0].time == wake_dt
        assert slots[1].time - slots[0].time == datetime.timedelta(hours=2)

    def test_taken_doses_appear_at_actual_times(self) -> None:
        """Taken doses show at real times, remaining projected from last."""
        tz = self._tz()
        taken_at = datetime.datetime(2025, 1, 1, 8, 15, tzinfo=tz)
        now = datetime.datetime(2025, 1, 1, 9, 30, tzinfo=tz)
        slots = build_adaptive_schedule(
            day=1,
            sleep_time=datetime.time(23, 0),
            wake_time=datetime.time(7, 0),
            timezone=TZ,
            taken_times=[taken_at],
            now=now,
        )
        assert slots[0].taken is True
        assert slots[0].time == taken_at
        assert slots[1].taken is False
        # Next projected from taken_at + 2h (phase 1 interval)
        assert slots[1].time == taken_at + datetime.timedelta(hours=2)
        assert len(slots) == 6

    def test_all_doses_taken(self) -> None:
        """When all doses taken, only taken slots returned."""
        tz = self._tz()
        now = datetime.datetime(2025, 1, 1, 20, 0, tzinfo=tz)
        taken = [
            datetime.datetime(2025, 1, 1, 8, 0, tzinfo=tz),
            datetime.datetime(2025, 1, 1, 10, 5, tzinfo=tz),
            datetime.datetime(2025, 1, 1, 12, 10, tzinfo=tz),
            datetime.datetime(2025, 1, 1, 14, 15, tzinfo=tz),
            datetime.datetime(2025, 1, 1, 16, 20, tzinfo=tz),
            datetime.datetime(2025, 1, 1, 18, 30, tzinfo=tz),
        ]
        slots = build_adaptive_schedule(
            day=1,
            sleep_time=datetime.time(23, 0),
            wake_time=datetime.time(7, 0),
            timezone=TZ,
            taken_times=taken,
            now=now,
        )
        assert all(s.taken for s in slots)
        assert len(slots) == 6
        for s, t in zip(slots, taken):
            assert s.time == t

    def test_projected_doses_extend_past_sleep_time(self) -> None:
        """All target tablets are shown even if they extend past sleep time."""
        tz = self._tz()
        taken_at = datetime.datetime(2025, 1, 1, 21, 0, tzinfo=tz)
        now = datetime.datetime(2025, 1, 1, 21, 30, tzinfo=tz)
        slots = build_adaptive_schedule(
            day=1,
            sleep_time=datetime.time(23, 0),
            wake_time=datetime.time(7, 0),
            timezone=TZ,
            taken_times=[taken_at],
            now=now,
        )
        # 1 taken + 5 projected = 6 total (phase 1 target)
        assert len(slots) == 6
        assert slots[0].taken is True
        # Projected slots extend past sleep_time (23:00)
        assert slots[-1].time > datetime.datetime(2025, 1, 1, 23, 0, tzinfo=tz)

    def test_phase2_interval(self) -> None:
        """Phase 2 (day 5) uses 2.5h interval for projections."""
        tz = self._tz()
        taken_at = datetime.datetime(2025, 1, 5, 8, 0, tzinfo=tz)
        now = datetime.datetime(2025, 1, 5, 9, 0, tzinfo=tz)
        slots = build_adaptive_schedule(
            day=5,
            sleep_time=datetime.time(23, 0),
            wake_time=datetime.time(7, 0),
            timezone=TZ,
            taken_times=[taken_at],
            now=now,
        )
        assert slots[0].time == taken_at
        assert slots[1].time == taken_at + datetime.timedelta(minutes=150)  # 2.5h
