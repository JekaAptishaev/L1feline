from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import User

# Создаем роутер для обработки команд
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /start. Регистрирует нового пользователя или приветствует существующего."""
    
    # Проверяем, есть ли пользователь в базе данных
    user_stmt = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = user_stmt.scalar_one_or_none()

    if not user:
        # Если пользователя нет, регистрируем его
        new_user = User(
            telegram_id=message.from_user.id,
            telegram_username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        session.add(new_user)
        await session.commit()

        # Отправляем приветственное сообщение
        await message.answer(
            "👋 Добро пожаловать! Вы успешно зарегистрированы.\n\n"
            "Теперь вы можете:\n"
            "🔹 Создать свою группу и стать её старостой\n"
            "🔹 Присоединиться к существующей группе по ссылке-приглашению"
        )
    else:
        # Если пользователь уже зарегистрирован, просто приветствуем его
        await message.answer(f"✨ С возвращением, {message.from_user.first_name}!")
