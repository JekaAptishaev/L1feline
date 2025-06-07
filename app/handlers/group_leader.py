import logging
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_main_menu_leader
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

class CreateGroup(StatesGroup):
    waiting_for_name = State()

class JoinGroup(StatesGroup):
    waiting_for_invite_link = State()

class CreateEvent(StatesGroup):
    waiting_for_event_name = State()
    waiting_for_event_date = State()
    waiting_for_description = State()
    waiting_for_subject = State()
    waiting_for_importance = State()

@router.message(CreateGroup.waiting_for_name)
async def process_group_name(message: Message, state: FSMContext, group_repo: GroupRepo):
    logger.info(f"Получено сообщение для CreateGroup.waiting_for_name: {message.text}")
    try:
        group_name = message.text.strip()
        if len(group_name) < 3:
            await message.answer("Название слишком короткое. Пожалуйста, введите название от 3 символов.")
            return
        if len(group_name) > 255:
            await message.answer("Название слишком длинное. Пожалуйста, введите название до 255 символов.")
            return

        await group_repo.create_group(name=group_name, creator_id=message.from_user.id)

        await state.clear()
        await message.answer(
            f"🎉 Группа «{group_name}» успешно создана! Вы теперь её староста.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_group_name: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при создании группы. Попробуйте позже.")

@router.message(JoinGroup.waiting_for_invite_link)
async def process_invite_link(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        invite_link = message.text.strip()
        match = re.match(r'^https://t\.me/\+[a-zA-Z0-9-]+$', invite_link) or re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', invite_link)
        if not match:
            await message.answer("Неверный формат пригласительной ссылки. Попробуйте еще раз.")
            return

        group_id = invite_link if match.group(0).startswith('{') else invite_link.split('+')[-1]
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user:
            user = await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )

        group = await group_repo.get_group_by_id(group_id)
        if not group:
            await message.answer("Группа не найдена. Проверьте ссылку.")
            return

        await group_repo.add_member(group_id=group.id, user_id=user.telegram_id, is_leader=False)
        await state.clear()
        await message.answer(f"Вы успешно присоединились к группе «{group.name}»!")
    except Exception as e:
        logger.error(f"Ошибка в process_invite_link: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при присоединении. Попробуйте позже.")

@router.message(F.text == "📅 События и Бронь")
async def handle_events_and_booking(message: Message, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
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

@router.message(F.text == "➕ Создать событие")
async def start_create_event(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        logger.info(f"User check for event creation: {user}, membership: {user.group_membership if user else None}")
        if not user or not user.group_membership or not user.group_membership.is_leader:
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
        try:
            date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()  # Преобразование строки в объект date
            event_date = date_obj  # Сохраняем объект date
        except ValueError:
            await message.answer("Неверный формат даты. Используйте YYYY-MM-DD (например, 2025-07-06).")
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
        event_date = data.get("date")  # Теперь это объект datetime.date
        description = data.get("description")
        subject = data.get("subject")
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user and user.group_membership:
            await group_repo.create_event(
                group_id=user.group_membership.group.id,
                created_by_user_id=user.telegram_id,
                title=event_name,
                description=description,
                subject=subject,
                date=event_date,  # Передаём объект date
                is_important=is_important
            )
            await state.clear()
            await message.answer(f"Событие «{event_name}» на {event_date.strftime('%Y-%m-%d')} создано! {'[Важное]' if is_important else ''}")
    except Exception as e:
        logger.error(f"Ошибка в process_event_importance: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")