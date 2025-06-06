from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.db.repository import UserRepo

router = Router()

@router.message(Command("admin_panel"))
async def show_admin_panel(message: Message, user_repo: UserRepo):
    # Здесь можно добавить проверку, является ли пользователь администратором
    await message.answer("Добро пожаловать в админ-панель!")