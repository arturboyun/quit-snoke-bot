import datetime

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class CravingLog(Base):
    __tablename__ = "craving_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
    )
