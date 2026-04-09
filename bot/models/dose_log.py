import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base


class DoseLog(Base):
    __tablename__ = "dose_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scheduled_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    taken: Mapped[bool] = mapped_column(Boolean, default=False)
    taken_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="dose_logs")  # noqa: F821
