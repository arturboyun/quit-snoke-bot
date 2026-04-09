"""Course management service — create, query, log doses."""

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.achievement import Achievement
from bot.models.course import Course, CourseStatus
from bot.models.craving_log import CravingLog
from bot.models.dose_log import DoseLog
from bot.models.mood_log import MoodLog
from bot.models.relapse_log import RelapseLog
from bot.models.smoking_profile import SmokingProfile
from bot.models.user import User


async def get_or_create_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        session.add(user)
        await session.flush()
    return user


async def get_active_course(session: AsyncSession, user_id: int) -> Course | None:
    stmt = (
        select(Course)
        .options(selectinload(Course.user))
        .where(Course.user_id == user_id, Course.status == CourseStatus.ACTIVE)
        .order_by(Course.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def start_course(
    session: AsyncSession,
    user_id: int,
    start_date: datetime.date,
) -> Course:
    # Cancel any existing active course
    active = await get_active_course(session, user_id)
    if active:
        active.status = CourseStatus.CANCELLED

    course = Course(user_id=user_id, start_date=start_date)
    session.add(course)
    await session.flush()
    return course


async def log_dose(
    session: AsyncSession,
    course_id: int,
    user_id: int,
    scheduled_at: datetime.datetime,
    day: int,
    phase: int,
) -> DoseLog:
    dose = DoseLog(
        course_id=course_id,
        user_id=user_id,
        scheduled_at=scheduled_at,
        taken=True,
        taken_at=datetime.datetime.now(datetime.UTC),
        day=day,
        phase=phase,
    )
    session.add(dose)
    await session.flush()
    return dose


async def get_doses_taken_today(
    session: AsyncSession,
    course_id: int,
    target_date: datetime.date,
) -> int:
    course = await session.get(Course, course_id)
    if course is None:
        return 0
    day = (target_date - course.start_date).days + 1
    stmt = select(DoseLog).where(
        DoseLog.course_id == course_id,
        DoseLog.taken.is_(True),
        DoseLog.day == day,
    )
    result = await session.execute(stmt)
    return len(result.scalars().all())


async def update_user_settings(
    session: AsyncSession,
    user_id: int,
    *,
    timezone: str | None = None,
    wake_time: datetime.time | None = None,
    sleep_time: datetime.time | None = None,
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    if timezone is not None:
        user.timezone = timezone
    if wake_time is not None:
        user.wake_time = wake_time
    if sleep_time is not None:
        user.sleep_time = sleep_time
    await session.flush()
    return user


# ── Smoking Profile ──────────────────────────────────────────────────────────


async def get_smoking_profile(
    session: AsyncSession, user_id: int,
) -> SmokingProfile | None:
    stmt = select(SmokingProfile).where(SmokingProfile.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def save_smoking_profile(
    session: AsyncSession,
    user_id: int,
    cigarettes_per_day: int,
    pack_price: float,
    cigarettes_in_pack: int = 20,
) -> SmokingProfile:
    existing = await get_smoking_profile(session, user_id)
    if existing:
        existing.cigarettes_per_day = cigarettes_per_day
        existing.pack_price = pack_price
        existing.cigarettes_in_pack = cigarettes_in_pack
        await session.flush()
        return existing
    profile = SmokingProfile(
        user_id=user_id,
        cigarettes_per_day=cigarettes_per_day,
        pack_price=pack_price,
        cigarettes_in_pack=cigarettes_in_pack,
    )
    session.add(profile)
    await session.flush()
    return profile


# ── Craving Log ──────────────────────────────────────────────────────────────


async def log_craving(session: AsyncSession, user_id: int) -> CravingLog:
    entry = CravingLog(user_id=user_id)
    session.add(entry)
    await session.flush()
    return entry


async def get_craving_count(session: AsyncSession, user_id: int) -> int:
    stmt = select(func.count()).select_from(CravingLog).where(CravingLog.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar() or 0


# ── Mood Log ─────────────────────────────────────────────────────────────────


async def log_mood(session: AsyncSession, user_id: int, mood: str) -> MoodLog:
    entry = MoodLog(user_id=user_id, mood=mood)
    session.add(entry)
    await session.flush()
    return entry


async def get_mood_history(
    session: AsyncSession, user_id: int, limit: int = 7,
) -> list[MoodLog]:
    stmt = (
        select(MoodLog)
        .where(MoodLog.user_id == user_id)
        .order_by(MoodLog.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ── Relapse Log ──────────────────────────────────────────────────────────────


async def log_relapse(
    session: AsyncSession, user_id: int, cigarettes: int = 1,
) -> RelapseLog:
    entry = RelapseLog(user_id=user_id, cigarettes=cigarettes)
    session.add(entry)
    await session.flush()
    return entry


async def get_relapse_stats(session: AsyncSession, user_id: int) -> dict:
    stmt = select(RelapseLog).where(RelapseLog.user_id == user_id)
    result = await session.execute(stmt)
    entries = result.scalars().all()
    total_cigarettes = sum(e.cigarettes for e in entries)
    return {"count": len(entries), "total_cigarettes": total_cigarettes}


# ── Achievements ─────────────────────────────────────────────────────────────

ACHIEVEMENT_DEFS: dict[str, tuple[str, str]] = {
    "first_dose": ("💊 Первая таблетка", "Принял первую таблетку Табекс"),
    "day_1_smoke_free": ("🚭 Первый день", "Первый день без сигарет"),
    "day_3_smoke_free": ("💪 3 дня свободы", "3 дня без сигарет"),
    "day_7_smoke_free": ("🌟 Неделя свободы", "Целая неделя без сигарет!"),
    "day_14_smoke_free": ("🏅 2 недели", "2 недели без сигарет"),
    "doses_10": ("🔟 10 таблеток", "Принял 10 таблеток"),
    "doses_50": ("5️⃣0️⃣ 50 таблеток", "Принял 50 таблеток"),
    "doses_100": ("💯 100 таблеток", "Принял 100 таблеток"),
    "course_completed": ("🎓 Курс завершён", "Прошёл полный 25-дневный курс"),
    "craving_resisted_5": ("🛡️ Стойкость", "Противостоял тяге 5 раз"),
    "craving_resisted_20": ("🏆 Несгибаемый", "Противостоял тяге 20 раз"),
}


async def get_user_achievements(
    session: AsyncSession, user_id: int,
) -> list[Achievement]:
    stmt = (
        select(Achievement)
        .where(Achievement.user_id == user_id)
        .order_by(Achievement.earned_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def grant_achievement(
    session: AsyncSession, user_id: int, key: str,
) -> Achievement | None:
    """Grant an achievement if not already earned. Returns None if already exists."""
    stmt = select(Achievement).where(
        Achievement.user_id == user_id, Achievement.key == key,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return None
    achievement = Achievement(user_id=user_id, key=key)
    session.add(achievement)
    await session.flush()
    return achievement


async def check_and_grant_achievements(
    session: AsyncSession, user_id: int,
) -> list[str]:
    """Check all achievement conditions and grant new ones. Returns list of newly earned keys."""
    newly_earned: list[str] = []

    # Count total doses
    dose_count_stmt = select(func.count()).select_from(DoseLog).where(
        DoseLog.user_id == user_id, DoseLog.taken.is_(True),
    )
    result = await session.execute(dose_count_stmt)
    total_doses = result.scalar() or 0

    if total_doses >= 1:
        a = await grant_achievement(session, user_id, "first_dose")
        if a:
            newly_earned.append("first_dose")
    if total_doses >= 10:
        a = await grant_achievement(session, user_id, "doses_10")
        if a:
            newly_earned.append("doses_10")
    if total_doses >= 50:
        a = await grant_achievement(session, user_id, "doses_50")
        if a:
            newly_earned.append("doses_50")
    if total_doses >= 100:
        a = await grant_achievement(session, user_id, "doses_100")
        if a:
            newly_earned.append("doses_100")

    # Count cravings resisted
    craving_count = await get_craving_count(session, user_id)
    if craving_count >= 5:
        a = await grant_achievement(session, user_id, "craving_resisted_5")
        if a:
            newly_earned.append("craving_resisted_5")
    if craving_count >= 20:
        a = await grant_achievement(session, user_id, "craving_resisted_20")
        if a:
            newly_earned.append("craving_resisted_20")

    # Smoke-free days
    course = await get_active_course(session, user_id)
    if course:
        relapse_stats = await get_relapse_stats(session, user_id)
        if relapse_stats["total_cigarettes"] == 0:
            from bot.services.schedule import get_course_day

            today = datetime.date.today()
            day = get_course_day(course.start_date, today)
            smoke_free_days = max(0, day - 5)  # counting from quit day

            if smoke_free_days >= 1:
                a = await grant_achievement(session, user_id, "day_1_smoke_free")
                if a:
                    newly_earned.append("day_1_smoke_free")
            if smoke_free_days >= 3:
                a = await grant_achievement(session, user_id, "day_3_smoke_free")
                if a:
                    newly_earned.append("day_3_smoke_free")
            if smoke_free_days >= 7:
                a = await grant_achievement(session, user_id, "day_7_smoke_free")
                if a:
                    newly_earned.append("day_7_smoke_free")
            if smoke_free_days >= 14:
                a = await grant_achievement(session, user_id, "day_14_smoke_free")
                if a:
                    newly_earned.append("day_14_smoke_free")

    return newly_earned
