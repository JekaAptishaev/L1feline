from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.db.repository import UserRepo

router = Router()

@router.message(Command("assistant_menu"))
async def show_assistant_menu(message: Message, user_repo: UserRepo):
    user = await user_repo.get_user_with_group_info(message.from_user.id)
    if user and user.group_membership and user.group_membership.is_assistant:
        await message.answer("Меню ассистента группы. Вы можете управлять событиями.")
    else:
        await message.answer("У вас нет прав ассистента.")

@router.message(F.text == "📅 Управление событиями")
async def manage_events(message: Message, user_repo: UserRepo):
    user = await user_repo.get_user_with_group_info(message.from_user.id)
    if user and user.group_membership and user.group_membership.is_assistant:
        await message.answer("Выберите действие: ➕ Создать событие")
    else:
        await message.answer("У вас нет прав для управления событиями.")
