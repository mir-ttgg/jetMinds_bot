from datetime import datetime

from sqlalchemy import select, update

from database.config import AsyncSessionLocal
from database.models import User
from zoneinfo import ZoneInfo
from sqlalchemy.dialects.postgresql import insert


def now_utc():
    return datetime.now(ZoneInfo("UTC"))

async def add_user(user_id: int, username: str | None):
    """
    Добавляет нового пользователя или обновляет username существующего.
    """
    async with AsyncSessionLocal() as session:
        stmt = insert(User).values(
            user_id=user_id,
            username=username,
            registered_at=now_utc()  # ИСПРАВЛЕНО
        )
        do_update_stmt = stmt.on_conflict_do_update(
            index_elements=['user_id'],
            set_=dict(username=username)
        )
        await session.execute(do_update_stmt)
        await session.commit()

async def get_user_by_id(user_id: int):
    """Получить пользователя по ID"""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

async def user_completed_survey(user_id: int) -> bool:
    """Проверяет, прошёл ли пользователь опрос"""
    async with AsyncSessionLocal() as session:
        stmt = select(User.survey_completed).where(User.user_id == user_id)
        result = await session.execute(stmt)
        completed = result.scalar_one_or_none()
        return completed if completed else False

async def save_survey(user_id: int, qual: bool, **answers):
    """
    Сохраняет результаты опроса пользователя.
    """
    async with AsyncSessionLocal() as session:
        # Убираем явное перечисление ans_1, ans_2 и т.д.
        # Теперь функция принимает любые ответы из **answers
        values_to_update = {
            "qual": qual,
            "survey_completed": True,
            "survey_completed_at": now_utc(),  # ИСПРАВЛЕНО
            **answers
        }
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(**values_to_update)
        )
        await session.execute(stmt)
        await session.commit()

async def update_user_phone(user_id: int, phone: str):
    async with AsyncSessionLocal() as session:
        stmt = update(User).where(User.user_id == user_id).values(phone=phone)
        await session.execute(stmt)
        await session.commit()

async def update_user_comments(user_id: int, comments: str):
    async with AsyncSessionLocal() as session:
        stmt = update(User).where(User.user_id == user_id).values(comments=comments)
        await session.execute(stmt)
        await session.commit()

async def update_user_started_at(user_id: int):
    async with AsyncSessionLocal() as session:
        stmt = update(User).where(User.user_id == user_id).values(
            started_at=now_utc(),  # ИСПРАВЛЕНО
            reminder_10min_sent=False,
            reminder_2h_sent=False,
            reminder_24h_sent=False
        )
        await session.execute(stmt)
        await session.commit()

async def mark_reminder_sent(user_id: int, minutes: int):
    async with AsyncSessionLocal() as session:
        column_to_update = None
        if minutes == 10:
            column_to_update = "reminder_10min_sent"
        elif minutes == 120:
            column_to_update = "reminder_2h_sent"
        elif minutes == 1440:
            column_to_update = "reminder_24h_sent"
        else:
            return

        stmt = update(User).where(User.user_id == user_id).values({column_to_update: True})
        await session.execute(stmt)
        await session.commit()
