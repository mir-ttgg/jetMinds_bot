import sys
import asyncio
import logging

from os import getenv
from pathlib import Path

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.handers import router
from database.config import init_db
from app.handers import set_bot_instance

load_dotenv()


def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_level = getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger()
    logger.setLevel(numeric_level)

    logger.handlers.clear()

    log_file = log_dir / "bot.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    return logger


TOKEN = getenv('TOKEN')

dp = Dispatcher()
dp.include_router(router)


async def main() -> None:
    logger = setup_logging()
    logger.info("Запуск Telegram бота...")

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
