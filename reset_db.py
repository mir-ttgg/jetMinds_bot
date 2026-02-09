import asyncio
import sys
from pathlib import Path

from database.config import engine
from database.models import Base

# Добавляем корневую папку проекта в путь
sys.path.append(str(Path(__file__).parent.parent))


async def reset_database():
    """Удаляет и создаёт заново все таблицы"""
    async with engine.begin() as conn:
        # Удаляем все таблицы
        await conn.run_sync(Base.metadata.drop_all)
        print("🗑️  Старые таблицы удалены")

        # Создаём заново
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Новые таблицы созданы")


if __name__ == '__main__':
    asyncio.run(reset_database())
