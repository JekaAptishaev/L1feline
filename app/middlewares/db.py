import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.repository import UserRepo, GroupRepo  # Добавьте GroupRepo, если используете

logger = logging.getLogger(__name__)

class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(self, handler, event, data):
        logger.info("Начало DbSessionMiddleware")
        try:
            async with self.session_pool() as session:
                logger.info("Сессия создана")
                data["session"] = session
                data["user_repo"] = UserRepo(session)
                data["group_repo"] = GroupRepo(session)
                result = await handler(event, data)
                logger.info("Обработчик успешно выполнен")
                return result
        except Exception as e:
            logger.error(f"Ошибка в DbSessionMiddleware: {e}", exc_info=True)
            raise
        finally:
            logger.info("Сессия закрыта")