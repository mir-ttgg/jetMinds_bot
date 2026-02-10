from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from zoneinfo import ZoneInfo


def now_msk():
    return datetime.now(tz=ZoneInfo("Europe/Moscow"))


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_msk)
    
    phone: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    ans_1 = mapped_column(Text)
    ans_2 = mapped_column(Text)
    ans_3 = mapped_column(Text)
    ans_4 = mapped_column(Text)
    ans_5 = mapped_column(Text)
    ans_6 = mapped_column(Text)
    ans_7 = mapped_column(Text)
    ans_8 = mapped_column(Text)
    ans_9 = mapped_column(Text)

    comments = mapped_column(Text, nullable=True)
    qual = mapped_column(Boolean, default=False)

    survey_completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    survey_completed = mapped_column(Boolean, default=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    
    reminder_10min_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_2h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_24h_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self):
        return f"<User {self.user_id}>"
