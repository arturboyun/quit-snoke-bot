import datetime
import enum

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base


class CourseStatus(enum.StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[CourseStatus] = mapped_column(
        Enum(CourseStatus),
        default=CourseStatus.ACTIVE,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
    )

    user: Mapped["User"] = relationship(back_populates="courses")  # noqa: F821
    dose_logs: Mapped[list["DoseLog"]] = relationship(back_populates="course")  # noqa: F821
