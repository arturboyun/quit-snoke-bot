import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class SmokingProfile(Base):
    __tablename__ = "smoking_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, unique=True,
    )
    cigarettes_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    pack_price: Mapped[float] = mapped_column(Float, nullable=False)
    cigarettes_in_pack: Mapped[int] = mapped_column(Integer, default=20)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
    )
