import asyncio
import logging
import os
import sys
from datetime import datetime
from os import getenv
from pathlib import Path

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.handers import router, set_bot_instance
from database.config import init_db

load_dotenv()


def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"Создана папка для логов: {log_dir}")

    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    log_filename = f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setLevel(logging.INFO)
    # console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    # logger.addHandler(console_handler)

    return logger


TOKEN = getenv('TOKEN')

dp = Dispatcher()
dp.include_router(router)


async def main() -> None:
    logger = setup_logging()
    logger.info("Запуск бота...")

    bot = Bot(token=TOKEN)
    set_bot_instance(bot)

    try:
        await init_db()
        logger.info("База данных инициализирована")
        logger.info("Бот запущен и готов к работе")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта")

if __name__ == '__main__':
    asyncio.run(main())
