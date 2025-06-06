from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.db.repository import UserRepo

router = Router()

@router.message(Command("member_info"))
async def show_member_info(message: Message, user_repo: UserRepo):
    user = await user_repo.get_user_with_group_info(message.from_user.id)
    if user and user.group_membership:
        await message.answer(f"Вы участник группы «{user.group_membership.group.name}».")
    else:
        await message.answer("Вы не состоите в группе.")