import logging
from aiogram.fsm.context import FSMContext
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_regular_member_menu, get_main_menu_unregistered

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "🚪 Выйти из группы")
async def leave_group(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            return

        if user.group_membership.is_leader:
            await message.answer("Вы являетесь старостой группы. Чтобы удалить группу, используйте кнопку «Удалить группу».")
            return

        group = user.group_membership.group
        success = await group_repo.leave_group(group_id=str(group.id), user_id=user.telegram_id)
        if success:
            await state.clear()
            await message.answer(
                f"Вы успешно покинули группу «{group.name}».",
                reply_markup=get_main_menu_unregistered()
            )
        else:
            await message.answer("Не удалось покинуть группу. Возможно, вы лидер группы.")
    except Exception as e:
        logger.error(f"Ошибка в leave_group: {e}")
        await message.answer("Произошла ошибка при выходе из группы. Попробуйте позже.")

@router.message(F.text == "📅 События")
async def handle_events_and_booking(message: Message, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("У вас нет прав для управления событиями.")
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        if not events:
            await message.answer("События отсутствуют. Создайте новое событие.")
        else:
            event_list = "\n".join([f"- {e.title} ({e.date}) {'[Важное]' if e.is_important else ''}" for e in events])
            await message.answer(f"Список событий:\n{event_list}")
    except Exception as e:
        logger.error(f"Ошибка в handle_events_and_booking: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(Command("calendar"))
@router.message(F.text == "📅 Показать календарь")
async def show_calendar_member(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Перенаправление на месячный календарь для обычных участников."""
    try:
        from app.handlers import calendar
        await calendar.show_calendar(message, user_repo, group_repo, state)
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

        member_list = []
        for member in members:
            member_user = await user_repo.get_user_with_group_info(member.user_id)
            if member_user:
                role = "Староста" if member.is_leader else "Ассистент" if member.is_assistant else "Участник"
                full_name = f"{member_user.last_name or ''} {member_user.first_name} {member_user.middle_name or ''}".strip()
                member_info = f"{full_name} (@{member_user.telegram_username or 'без имени'}) - {role}"
                member_list.append(member_info)

        response = f"Участники группы «{group.name}»:\n" + "\n".join(member_list)
        await message.answer(response)
    except Exception as e:
        logger.error(f"Ошибка в handle_group_members: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка участников. Попробуйте позже.")
