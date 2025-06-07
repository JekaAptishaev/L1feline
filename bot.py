import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.handlers.group_leader import router as group_leader_router
from app.handlers import common
from app.middlewares.db import DbSessionMiddleware
from app.config import DATABASE_URL, BOT_TOKEN  # Импортируем напрямую из app.config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main() -> None:
    """Запуск бота и настройка всех компонентов."""
    logger.info("🚀 Запуск бота...")

    # Проверки уже выполнены в app/config.py, но можно оставить для логирования
    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL не найден в переменных окружения!")
        return
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        return

    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))
    dp.include_router(common.router)
    dp.include_router(group_leader_router)

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот остановлен!")