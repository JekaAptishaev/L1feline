import logging
from aiogram import Router
from aiogram.types import Message
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_calendar_keyboard  # Предполагаемая функция

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "📅 Показать календарь")
async def show_calendar(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)  # Предполагаемый метод
        calendar = get_calendar_keyboard(events)  # Предполагаемая функция в reply.py
        await message.answer("Календарь событий:", reply_markup=calendar)
    except Exception as e:
        logger.error(f"Ошибка в show_calendar: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")
