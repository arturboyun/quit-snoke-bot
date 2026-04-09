"""Tests for the course management service using a real SQLite async DB."""

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.course import CourseStatus
from bot.models.dose_log import DoseLog
from bot.services.course import (
    complete_course,
    get_active_course,
    get_course_history,
    get_last_dose_time,
    get_or_create_user,
    log_dose,
    log_missed_doses,
    start_course,
    update_user_settings,
)


class TestGetOrCreateUser:
    async def test_create_new_user(self, db_session: AsyncSession) -> None:
        user = await get_or_create_user(db_session, 12345)
        assert user.id == 12345
        assert user.timezone == "Europe/Kyiv"
        assert user.wake_time == datetime.time(8, 0)
        assert user.sleep_time == datetime.time(22, 0)

    async def test_return_existing_user(self, db_session: AsyncSession) -> None:
        user1 = await get_or_create_user(db_session, 12345)
        user2 = await get_or_create_user(db_session, 12345)
        assert user1.id == user2.id

    async def test_different_users(self, db_session: AsyncSession) -> None:
        user1 = await get_or_create_user(db_session, 111)
        user2 = await get_or_create_user(db_session, 222)
        assert user1.id != user2.id


class TestGetActiveCourse:
    async def test_no_active_course(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await get_active_course(db_session, 12345)
        assert course is None

    async def test_returns_active_course(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await start_course(db_session, 12345, datetime.date(2026, 1, 1))
        await db_session.flush()

        course = await get_active_course(db_session, 12345)
        assert course is not None
        assert course.status == CourseStatus.ACTIVE

    async def test_ignores_cancelled_course(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))
        course.status = CourseStatus.CANCELLED
        await db_session.flush()

        result = await get_active_course(db_session, 12345)
        assert result is None


class TestStartCourse:
    async def test_start_new_course(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 4, 1))
        assert course.user_id == 12345
        assert course.start_date == datetime.date(2026, 4, 1)
        assert course.status == CourseStatus.ACTIVE

    async def test_cancels_existing_active_course(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        old = await start_course(db_session, 12345, datetime.date(2026, 1, 1))
        new = await start_course(db_session, 12345, datetime.date(2026, 4, 1))

        await db_session.refresh(old)
        assert old.status == CourseStatus.CANCELLED
        assert new.status == CourseStatus.ACTIVE


class TestLogDose:
    async def test_log_dose(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        dose = await log_dose(
            db_session,
            course_id=course.id,
            user_id=12345,
            scheduled_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            day=1,
            phase=1,
        )
        assert dose.taken is True
        assert dose.taken_at is not None
        assert dose.day == 1
        assert dose.phase == 1
        assert dose.course_id == course.id

    async def test_multiple_doses(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        for hour in [8, 10, 12]:
            await log_dose(
                db_session,
                course_id=course.id,
                user_id=12345,
                scheduled_at=datetime.datetime(2026, 1, 1, hour, 0, tzinfo=datetime.UTC),
                day=1,
                phase=1,
            )

        from sqlalchemy import select

        result = await db_session.execute(select(DoseLog).where(DoseLog.course_id == course.id))
        assert len(result.scalars().all()) == 3


class TestUpdateUserSettings:
    async def test_update_timezone(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        user = await update_user_settings(db_session, 12345, timezone="Asia/Tokyo")
        assert user.timezone == "Asia/Tokyo"

    async def test_update_wake_time(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        user = await update_user_settings(
            db_session,
            12345,
            wake_time=datetime.time(7, 30),
        )
        assert user.wake_time == datetime.time(7, 30)

    async def test_update_sleep_time(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        user = await update_user_settings(
            db_session,
            12345,
            sleep_time=datetime.time(23, 0),
        )
        assert user.sleep_time == datetime.time(23, 0)

    async def test_update_multiple_fields(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        user = await update_user_settings(
            db_session,
            12345,
            timezone="Europe/London",
            wake_time=datetime.time(6, 0),
            sleep_time=datetime.time(21, 0),
        )
        assert user.timezone == "Europe/London"
        assert user.wake_time == datetime.time(6, 0)
        assert user.sleep_time == datetime.time(21, 0)

    async def test_update_nonexistent_user_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(ValueError, match="not found"):
            await update_user_settings(db_session, 99999, timezone="UTC")

    async def test_partial_update_preserves_other_fields(
        self,
        db_session: AsyncSession,
    ) -> None:
        await get_or_create_user(db_session, 12345)
        user = await update_user_settings(db_session, 12345, timezone="Asia/Tokyo")
        assert user.wake_time == datetime.time(8, 0)  # default preserved
        assert user.sleep_time == datetime.time(22, 0)  # default preserved


class TestLogMissedDoses:
    async def test_logs_all_missing(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        missed = await log_missed_doses(
            db_session, course.id, 12345, day=1, phase=1, total_expected=6
        )
        assert missed == 6

    async def test_partial_taken(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        # Take 2 doses on day 1
        for hour in [8, 10]:
            await log_dose(
                db_session,
                course_id=course.id,
                user_id=12345,
                scheduled_at=datetime.datetime(2026, 1, 1, hour, 0, tzinfo=datetime.UTC),
                day=1,
                phase=1,
            )

        missed = await log_missed_doses(
            db_session, course.id, 12345, day=1, phase=1, total_expected=6
        )
        assert missed == 4

    async def test_all_taken_returns_zero(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        for hour in [8, 10, 12, 14, 16, 18]:
            await log_dose(
                db_session,
                course_id=course.id,
                user_id=12345,
                scheduled_at=datetime.datetime(2026, 1, 1, hour, 0, tzinfo=datetime.UTC),
                day=1,
                phase=1,
            )

        missed = await log_missed_doses(
            db_session, course.id, 12345, day=1, phase=1, total_expected=6
        )
        assert missed == 0


class TestGetLastDoseTime:
    async def test_no_doses_returns_none(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        result = await get_last_dose_time(db_session, course.id, day=1)
        assert result is None

    async def test_returns_latest_taken_at(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        course = await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        for hour in [8, 10, 12]:
            await log_dose(
                db_session,
                course_id=course.id,
                user_id=12345,
                scheduled_at=datetime.datetime(2026, 1, 1, hour, 0, tzinfo=datetime.UTC),
                day=1,
                phase=1,
            )

        result = await get_last_dose_time(db_session, course.id, day=1)
        assert result is not None


class TestGetCourseHistory:
    async def test_empty_history(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        courses = await get_course_history(db_session, 12345)
        assert courses == []

    async def test_returns_all_courses(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await start_course(db_session, 12345, datetime.date(2026, 1, 1))
        await start_course(db_session, 12345, datetime.date(2026, 4, 1))

        courses = await get_course_history(db_session, 12345)
        assert len(courses) == 2


class TestCompleteCourse:
    async def test_completes_active_course(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        await start_course(db_session, 12345, datetime.date(2026, 1, 1))

        result = await complete_course(db_session, 12345)
        assert result is not None
        assert result.status == CourseStatus.COMPLETED

    async def test_no_active_course_returns_none(self, db_session: AsyncSession) -> None:
        await get_or_create_user(db_session, 12345)
        result = await complete_course(db_session, 12345)
        assert result is None
