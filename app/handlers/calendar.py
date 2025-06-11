# app/handlers/calendar.py
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_calendar_keyboard
from app.handlers.weekly_calendar import router as weekly_calendar_router  # Новый импорт
from datetime import datetime

router = Router()
router.include_router(weekly_calendar_router)  # Подключаем маршруты недельного календаря
logger = logging.getLogger(__name__)

@router.message(F.text == "📅 Показать календарь")
async def show_calendar(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        logger.info(f"Events retrieved for calendar: {[event.date for event in events]}")
        calendar = get_calendar_keyboard(events)
        await message.answer("Календарь событий:", reply_markup=calendar)
    except Exception as e:
        logger.error(f"Ошибка в show_calendar: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("event_"))
async def handle_event_details(callback: CallbackQuery, group_repo: GroupRepo):
    try:
        event_id = callback.data.replace("event_", "")
        event = await group_repo.get_event_by_id(event_id)
        if event:
            details = f"Детали события:\nНазвание: {event.title}\nДата: {event.date.strftime('%Y-%m-%d')}"
            if event.description:
                details += f"\nОписание: {event.description}"
            if event.subject:
                details += f"\nТема: {event.subject}"
            details += f"\n{'[Важное]' if event.is_important else ''}"
            await callback.message.edit_text(details)
        else:
            await callback.message.edit_text("Событие не найдено.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_event_details: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "back")
async def handle_back(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if user and user.group_membership:
            events = await group_repo.get_group_events(user.group_membership.group.id)
            calendar = get_calendar_keyboard(events)
            if calendar:
                await callback.message.edit_reply_markup(reply_markup=calendar)
            else:
                await callback.message.edit_text("Не удалось загрузить календарь.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_back: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)