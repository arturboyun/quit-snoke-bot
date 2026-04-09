import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Kyiv")
    wake_time: Mapped[datetime.time] = mapped_column(default=datetime.time(8, 0))
    sleep_time: Mapped[datetime.time] = mapped_column(default=datetime.time(22, 0))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
    )

    courses: Mapped[list["Course"]] = relationship(back_populates="user")  # noqa: F821
