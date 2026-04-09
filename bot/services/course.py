"""Course management service — create, query, log doses."""

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.course import Course, CourseStatus
from bot.models.dose_log import DoseLog
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
