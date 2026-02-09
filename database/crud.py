from datetime import datetime

from sqlalchemy import select, update

from database.config import async_session
from database.models import User


async def add_user(user_id: int, username: str):
    """Добавляет нового пользователя или возвращает существующего"""
    async with async_session() as session:
        stmt = select(User).where(User.user_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            return user

        new_user = User(
            user_id=user_id,
            username=username,
            registered_at=datetime.now()
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user


async def get_user_by_id(user_id: int):
    """Получить пользователя по ID"""
    async with async_session() as session:
        stmt = select(User).where(User.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_survey_by_user_id(user_id: int):
    """Получить ответы на опрос по ID пользователя"""
    async with async_session() as session:
        stmt = select(User).where(User.user_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user


async def user_completed_survey(user_id: int) -> bool:
    """Проверяет, прошёл ли пользователь опрос"""
    async with async_session() as session:
        stmt = select(User.survey_completed).where(User.user_id == user_id)
        result = await session.execute(stmt)
        completed = result.scalar_one_or_none()
        return completed if completed else False


async def save_survey(
    user_id: int,
    ans_1: str,
    ans_2: str,
    ans_3: str,
    ans_4: str,
    ans_5: str,
    ans_6: str,
    ans_7: str,
    ans_8: str,
    ans_9: str,
    qual: bool,
):
    async with async_session() as session:
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(
                ans_1=ans_1,
                ans_2=ans_2,
                ans_3=ans_3,
                ans_4=ans_4,
                ans_5=ans_5,
                ans_6=ans_6,
                ans_7=ans_7,
                ans_8=ans_8,
                ans_9=ans_9,
                qual=qual,
                survey_completed_at=datetime.now(),
                survey_completed=True
            )
        )
        await session.execute(stmt)
        await session.commit()


async def update_user_phone(user_id: int, phone: str):
    async with async_session() as session:
        stmt = update(User).where(User.user_id == user_id).values(phone=phone)
        await session.execute(stmt)
        await session.commit()


async def update_user_comments(user_id: int, comments: str):
    async with async_session() as session:
        stmt = update(User).where(User.user_id ==
                                  user_id).values(comments=comments)
        await session.execute(stmt)
        await session.commit()


async def update_user_started_at(user_id: int):
    async with async_session() as session:
        stmt = update(User).where(User.user_id == user_id).values(
            started_at=datetime.now(),
            reminder_10min_sent=False,
            reminder_2h_sent=False,
            reminder_24h_sent=False
        )
        await session.execute(stmt)
        await session.commit()


async def get_users_with_active_survey():
    async with async_session() as session:
        stmt = select(User).where(
            User.survey_completed == True,
            User.qual == True,
            User.phone.is_not(None),
            User.comments.is_not(None)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


async def mark_reminder_sent(user_id: int, minutes: int):
    async with async_session() as session:
        if minutes == 10:
            stmt = update(User).where(User.user_id == user_id).values(
                reminder_10min_sent=True)
        elif minutes == 120:
            stmt = update(User).where(User.user_id ==
                                      user_id).values(reminder_2h_sent=True)
        elif minutes == 1440:
            stmt = update(User).where(User.user_id == user_id).values(
                reminder_24h_sent=True)
        else:
            return

        await session.execute(stmt)
        await session.commit()
