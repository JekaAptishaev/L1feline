import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.repository import UserRepo, GroupRepo  # Добавьте GroupRepo, если используете

logger = logging.getLogger(__name__)

class DbSessionMiddleware(BaseMiddleware):
    """Middleware для передачи асинхронной сессии SQLAlchemy в обработчики событий."""
    
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Добавляет сессию базы данных и репозитории в data и вызывает обработчик."""
        try:
            async with self.session_pool() as session:
                data["session"] = session
                data["user_repo"] = UserRepo(session)
                # Если GroupRepo нужен, раскомментируйте:
                data["group_repo"] = GroupRepo(session)
                return await handler(event, data)
        except Exception as e:
            logger.error(f"Ошибка в DbSessionMiddleware: {e}")
            raise