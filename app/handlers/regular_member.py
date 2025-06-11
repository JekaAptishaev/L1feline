import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_regular_member_menu

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("start_menu"))
async def show_menu(message: Message, user_repo: UserRepo):
    """Обработчик команды /start_menu для отображения меню обычного участника."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user and user.group_membership:
            await message.answer(
                f"Вы участник группы «{user.group_membership.group.name}». Выберите действие:",
                reply_markup=get_regular_member_menu()
            )
        else:
            await message.answer("Вы не состоите в группе.")
    except Exception as e:
        logger.error(f"Ошибка в show_menu: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

'''
@router.message(Command("member_info"))
@router.message(F.text == "ℹ️ Информация о группе")
async def show_member_info(message: Message, user_repo: UserRepo):
    """Обработчик для отображения информации о группе."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user and user.group_membership:
            await message.answer(f"Вы участник группы «{user.group_membership.group.name}».")
        else:
            await message.answer("Вы не состоите в группе.")
    except Exception as e:
        logger.error(f"Ошибка в show_member_info: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")
'''

@router.message(Command("calendar"))
@router.message(F.text == "📅 Показать календарь")
async def show_calendar_member(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    """Перенаправление на месячный календарь для обычных участников."""
    try:
        from app.handlers import calendar
        await calendar.show_calendar(message, user_repo, group_repo)
    except Exception as e:
        logger.error(f"Ошибка в show_calendar_member: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(Command("weekly_calendar"))
@router.message(F.text == "📅 Показать недельный календарь")
async def show_weekly_calendar_member(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    """Перенаправление на недельный календарь для обычных участников."""
    try:
        from app.handlers.weekly_calendar import show_weekly_calendar
        await show_weekly_calendar(message, user_repo, group_repo)
    except Exception as e:
        logger.error(f"Ошибка в show_weekly_calendar_member: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "👥 Участники группы")
async def handle_group_members_leader(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик: отображение списка участников группы с ролями."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("У вас нет прав для просмотра участников группы.")
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await message.answer("В группе пока нет участников.")
            return

        # Формируем список участников
        member_list = []
        for member in members:
            member_user = await user_repo.get_user_with_group_info(member.user_id)
            if member_user:
                role = "Староста" if member.is_leader else "Ассистент" if member.is_assistant else "Участник"
                member_info = f"{member_user.first_name} {member_user.last_name or ''} (@{member_user.telegram_username or 'без имени'}) - {role}"
                member_list.append(member_info)

        response = f"Участники группы «{group.name}»:\n" + "\n".join(member_list)
        await message.answer(response)
    except Exception as e:
        logger.error(f"Ошибка в handle_group_members: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка участников. Попробуйте позже.")
