import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_weekly_calendar_keyboard, get_weekly_calendar_back_button
from datetime import datetime, timedelta

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("weekly_calendar"))
async def show_weekly_calendar(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик команды /weekly_calendar для отображения календаря по неделям."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            return

        group = user.group_membership.group
        # Текущая неделя начинается с понедельника
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        events = await group_repo.get_group_events(group.id)
        logger.info(f"Events retrieved for weekly calendar: {[event.date for event in events]}")
        calendar = get_weekly_calendar_keyboard(events, start_of_week)
        await message.answer(f"Календарь событий группы «{group.name}» (неделя с {start_of_week.strftime('%Y-%m-%d')}):", reply_markup=calendar)
    except Exception as e:
        logger.error(f"Ошибка в show_weekly_calendar: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("week_"))
async def handle_week_navigation(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик переключения недель."""
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        week_offset = int(callback.data.split("_")[1])
        start_of_week = (datetime.now().date() - timedelta(days=datetime.now().date().weekday())) + timedelta(weeks=week_offset)
        events = await group_repo.get_group_events(group.id)
        calendar = get_weekly_calendar_keyboard(events, start_of_week)
        await callback.message.edit_text(
            f"Календарь событий группы «{group.name}» (неделя с {start_of_week.strftime('%Y-%m-%d')}):",
            reply_markup=calendar
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_week_navigation: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("event_"))
async def handle_event_details(callback: CallbackQuery, group_repo: GroupRepo):
    """Обработчик для отображения деталей события."""
    try:
        event_id = callback.data.replace("event_", "")
        event = await group_repo.get_event_by_id(event_id)
        if event:
            details = (
                f"Детали события:\n"
                f"Название: {event.title}\n"
                f"Дата: {event.date.strftime('%Y-%m-%d')}\n"
            )
            if event.description:
                details += f"Описание: {event.description}\n"
            if event.subject:
                details += f"Тема: {event.subject}\n"
            details += f"{'[Важное]' if event.is_important else ''}"
            await callback.message.edit_text(details, reply_markup=get_weekly_calendar_back_button())
        else:
            await callback.message.edit_text("Событие не найдено.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_event_details: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "week_back")
async def handle_week_back(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик возврата к календарю."""
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        events = await group_repo.get_group_events(group.id)
        calendar = get_weekly_calendar_keyboard(events, start_of_week)
        await callback.message.edit_text(
            f"Календарь событий группы «{group.name}» (неделя с {start_of_week.strftime('%Y-%m-%d')}):",
            reply_markup=calendar
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_week_back: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)