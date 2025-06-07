import logging
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_calendar_keyboard  # Предполагаем, что эта функция доступна

router = Router()
logger = logging.getLogger(__name__)

class CreateEvent(StatesGroup):
    waiting_for_event_name = State()
    waiting_for_event_date = State()
    waiting_for_description = State()
    waiting_for_subject = State()
    waiting_for_importance = State()

@router.message(Command("assistant_menu"))
async def show_assistant_menu(message: Message, user_repo: UserRepo):
    user = await user_repo.get_user_with_group_info(message.from_user.id)
    if user and user.group_membership and user.group_membership.is_assistant:
        await message.answer("Меню ассистента группы. Вы можете управлять событиями и просматривать календарь.")
    else:
        await message.answer("У вас нет прав ассистента.")

@router.message(F.text == "📅 Управление событиями")
async def manage_events(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    user = await user_repo.get_user_with_group_info(message.from_user.id)
    if user and user.group_membership and user.group_membership.is_assistant:
        await message.answer("Выберите действие:\n➕ Создать событие\n📅 Показать календарь", reply_markup=get_main_menu_leader())
    else:
        await message.answer("У вас нет прав для управления событиями.")

@router.message(F.text == "➕ Создать событие")
async def start_create_event(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_assistant:
            await message.answer("У вас нет прав для создания событий.")
            return

        await state.set_state(CreateEvent.waiting_for_event_name)
        await message.answer("Введите название события:")
    except Exception as e:
        logger.error(f"Ошибка в start_create_event: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateEvent.waiting_for_event_name)
async def process_event_name(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        event_name = message.text.strip()
        if len(event_name) < 3 or len(event_name) > 100:
            await message.answer("Название события должно быть от 3 до 100 символов.")
            return

        await state.update_data(event_name=event_name)
        await state.set_state(CreateEvent.waiting_for_event_date)
        await message.answer("Введите дату события (например, 2025-06-15):")
    except Exception as e:
        logger.error(f"Ошибка в process_event_name: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateEvent.waiting_for_event_date)
async def process_event_date(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        event_date = message.text.strip()
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', event_date):
            await message.answer("Неверный формат даты. Используйте YYYY-MM-DD.")
            return

        await state.update_data(date=event_date)
        await state.set_state(CreateEvent.waiting_for_description)
        await message.answer("Введите описание события (или 'Пропустить'):")
    except Exception as e:
        logger.error(f"Ошибка в process_event_date: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateEvent.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        description = message.text.strip() if message.text.strip().lower() != "пропустить" else None
        await state.update_data(description=description)
        await state.set_state(CreateEvent.waiting_for_subject)
        await message.answer("Введите тему события (или 'Пропустить'):")
    except Exception as e:
        logger.error(f"Ошибка в process_event_description: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateEvent.waiting_for_subject)
async def process_event_subject(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        subject = message.text.strip() if message.text.strip().lower() != "пропустить" else None
        await state.update_data(subject=subject)
        await state.set_state(CreateEvent.waiting_for_importance)
        await message.answer("Является ли событие важным? (Да/Нет)")
    except Exception as e:
        logger.error(f"Ошибка в process_event_subject: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateEvent.waiting_for_importance)
async def process_event_importance(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        is_important = message.text.strip().lower() in ["да", "yes"]
        data = await state.get_data()
        event_name = data.get("event_name")
        event_date = data.get("date")
        description = data.get("description")
        subject = data.get("subject")
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user and user.group_membership:
            await group_repo.create_event(
                group_id=user.group_membership.group.id,
                created_by_user_id=user.telegram_id,  # Временное решение, замените на user.id, если используете UUID
                title=event_name,
                description=description,
                subject=subject,
                date=event_date,
                is_important=is_important
            )
            await state.clear()
            await message.answer(f"Событие «{event_name}» на {event_date} создано! {'[Важное]' if is_important else ''}")
    except Exception as e:
        logger.error(f"Ошибка в process_event_importance: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "📅 Показать календарь")
async def show_calendar_assistant(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_assistant:
            await message.answer("У вас нет прав для просмотра календаря.")
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        calendar = get_calendar_keyboard(events)
        await message.answer("Календарь событий:", reply_markup=calendar)
    except Exception as e:
        logger.error(f"Ошибка в show_calendar_assistant: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")
