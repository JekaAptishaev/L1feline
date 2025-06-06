from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """Middleware для передачи асинхронной сессии SQLAlchemy в хэндлеры."""

    def __init__(self, session_pool: async_sessionmaker) -> None:
        """Инициализация middleware с пулом сессий."""
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Передача сессии в обработчик события."""
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)
