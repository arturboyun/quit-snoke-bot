"""Tabex 25-day protocol schedule calculator.

All dose scheduling logic lives here. Handlers must NOT contain protocol math.
"""

import datetime
from dataclasses import dataclass
from zoneinfo import ZoneInfo

# Phase definitions: (start_day, end_day, interval_minutes, target_tablets, min_tablets)
PHASES: list[tuple[int, int, int, int, int]] = [
    (1, 3, 120, 6, 6),    # Phase 1: days 1–3, every 2h, 6 tablets/day
    (4, 12, 150, 5, 5),   # Phase 2: days 4–12, every 2.5h, 5 tablets/day
    (13, 16, 180, 4, 4),  # Phase 3: days 13–16, every 3h, 4 tablets/day
    (17, 20, 300, 3, 3),  # Phase 4: days 17–20, every 5h, 3 tablets/day
    (21, 25, 300, 2, 1),  # Phase 5: days 21–25, every 5h, 1–2 tablets/day
]

COURSE_DAYS = 25
QUIT_DAY = 5


@dataclass(frozen=True)
class PhaseInfo:
    phase: int
    start_day: int
    end_day: int
    interval_minutes: int
    target_tablets: int
    min_tablets: int

    @property
    def target_display(self) -> str:
        """Display string for target tablets (e.g. '5' or '1–2')."""
        if self.min_tablets == self.target_tablets:
            return str(self.target_tablets)
        return f"{self.min_tablets}–{self.target_tablets}"


@dataclass(frozen=True)
class DoseSlot:
    time: datetime.datetime
    day: int
    phase: int


def get_phase(day: int) -> PhaseInfo:
    """Return phase info for a given course day (1-based)."""
    for i, (start, end, interval, tablets, min_tab) in enumerate(PHASES, start=1):
        if start <= day <= end:
            return PhaseInfo(
                phase=i,
                start_day=start,
                end_day=end,
                interval_minutes=interval,
                target_tablets=tablets,
                min_tablets=min_tab,
            )
    raise ValueError(f"Day {day} is outside the 25-day course (valid: 1–{COURSE_DAYS})")


def get_course_day(start_date: datetime.date, current_date: datetime.date) -> int:
    """Return the 1-based course day number."""
    return (current_date - start_date).days + 1


def is_quit_day(day: int) -> bool:
    """Day 5: user MUST stop smoking completely."""
    return day >= QUIT_DAY


def is_first_day_of_phase(day: int) -> bool:
    """Return True if this day is the first day of a new phase (transition day)."""
    return day in {phase[0] for phase in PHASES}


def calculate_dose_times(
    day: int,
    wake_time: datetime.time,
    sleep_time: datetime.time,
    course_start_date: datetime.date,
    timezone: str,
) -> list[DoseSlot]:
    """Calculate dose times for a specific course day.

    Doses start at wake_time, spaced by the phase interval,
    and stop before sleep_time.
    """
    phase = get_phase(day)
    tz = ZoneInfo(timezone)
    target_date = course_start_date + datetime.timedelta(days=day - 1)

    wake_dt = datetime.datetime.combine(target_date, wake_time, tzinfo=tz)
    sleep_dt = datetime.datetime.combine(target_date, sleep_time, tzinfo=tz)

    # Handle overnight waking (e.g., wake 22:00, sleep 06:00) — unlikely but safe
    if sleep_dt <= wake_dt:
        sleep_dt += datetime.timedelta(days=1)

    interval = datetime.timedelta(minutes=phase.interval_minutes)
    slots: list[DoseSlot] = []
    current = wake_dt

    while current < sleep_dt and len(slots) < phase.target_tablets:
        slots.append(DoseSlot(time=current, day=day, phase=phase.phase))
        current += interval

    return slots


def calculate_remaining_doses_today(
    day: int,
    wake_time: datetime.time,
    sleep_time: datetime.time,
    course_start_date: datetime.date,
    timezone: str,
    now: datetime.datetime | None = None,
) -> list[DoseSlot]:
    """Return only future dose slots for today (after `now`)."""
    all_slots = calculate_dose_times(day, wake_time, sleep_time, course_start_date, timezone)
    if now is None:
        now = datetime.datetime.now(ZoneInfo(timezone))
    return [s for s in all_slots if s.time > now]


def get_progress(day: int, doses_taken_today: int) -> dict[str, int | float | str]:
    """Return progress stats for the current day."""
    phase = get_phase(day)
    return {
        "day": day,
        "total_days": COURSE_DAYS,
        "phase": phase.phase,
        "doses_taken": doses_taken_today,
        "doses_target": phase.target_display,  # Phase 5: "1–2", others: "6", "5", etc.
        "percent_complete": round((day - 1) / COURSE_DAYS * 100, 1),
    }
