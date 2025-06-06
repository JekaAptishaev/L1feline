import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Импортируем наши роутеры и middleware
from app.handlers import common
from app.middlewares.db import DbSessionMiddleware

# Загружаем переменные окружения из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Запуск бота и настройка всех компонентов."""
    
    logger.info("🚀 Запуск бота...")

    # Создаем асинхронный движок для SQLAlchemy
    database_url = getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ DATABASE_URL не найден в переменных окружения!")
        return

    engine = create_async_engine(database_url, echo=False)  # echo=True для отладки SQL-запросов
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    # Создаем объекты Бота и Диспетчера
    bot_token = getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        return

    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем middleware для передачи сессии в хэндлеры
    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))

    # Регистрируем роутеры
    dp.include_router(common.router)
    # dp.include_router(group_leader.router)  # <- так вы будете добавлять новые модули
    # dp.include_router(admin.router)

    # Удаляем вебхук и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот остановлен!")
