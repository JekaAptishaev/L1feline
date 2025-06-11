import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_main_menu_leader, get_regular_member_menu
from datetime import datetime, timedelta
import uuid

router = Router()
logger = logging.getLogger(__name__)

class CreateInvite(StatesGroup):
    waiting_for_invite_duration = State()

@router.message(F.text == "👥 Участники группы*")
async def handle_group_members(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
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
                member_info = f"{member_user.first_name} {member_user.last_name or ''} (@{member_user.telegram_username or 'без имени'}) - {role}"
                member_list.append(member_info)

        response = f"Участники группы «{group.name}»:\n" + "\n".join(member_list)
        await message.answer(response)
    except Exception as e:
        logger.error(f"Ошибка в handle_group_members: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка участников. Попробуйте позже.")

@router.message(F.text == "🔗 Создать приглашение")
async def start_create_invite(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("У вас нет прав для создания ключей доступа.")
            return

        group = user.group_membership.group
        
        invite_token = await group_repo.create_invite(group.id, user.telegram_id)
        await state.clear()
        await message.answer(
            f"Ключ доступа создан!\nКлюч: {invite_token}\nПередайте этот ключ пользователям для присоединения к группе «{group.name}»."
        )
    except Exception as e:
        logger.error(f"Ошибка в start_create_invite: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при создании ключа доступа. Попробуйте позже.")

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
            date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
            event_date = date_obj
        except ValueError:
            await message.answer("Неверный формат даты. Используйте YYYY-MM-DD (например, 2025-07-06).")
            return

        await state.update_data(date=event_date)
        await state.set_state(CreateEvent.waiting_for_description)
        # Создаем инлайн-клавиатуру с кнопкой "Пропустить"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Пропустить", callback_data="skip_description")
        await message.answer("Введите описание события:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_event_date: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        await state.update_data(description=None)
        await state.set_state(CreateEvent.waiting_for_subject)
        # Создаем инлайн-клавиатуру с кнопкой "Пропустить"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Пропустить", callback_data="skip_subject")
        await callback.message.edit_text("Введите тему события:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в skip_description: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        description = message.text.strip()
        await state.update_data(description=description)
        await state.set_state(CreateEvent.waiting_for_subject)
        # Создаем инлайн-клавиатуру с кнопкой "Пропустить"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Пропустить", callback_data="skip_subject")
        await message.answer("Введите тему события:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_event_description: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "skip_subject")
async def skip_subject(callback: CallbackQuery, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        await state.update_data(subject=None)
        await state.set_state(CreateEvent.waiting_for_importance)
        # Создаем инлайн-клавиатуру с кнопками "Да" и "Нет"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Да", callback_data="importance_yes")
        keyboard.button(text="Нет", callback_data="importance_no")
        await callback.message.edit_text("Является ли событие важным?", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в skip_subject: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_subject)
async def process_event_subject(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        subject = message.text.strip()
        await state.update_data(subject=subject)
        await state.set_state(CreateEvent.waiting_for_importance)
        # Создаем инлайн-клавиатуру с кнопками "Да" и "Нет"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Да", callback_data="importance_yes")
        keyboard.button(text="Нет", callback_data="importance_no")
        await message.answer("Является ли событие важным?", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_event_subject: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.in_(["importance_yes", "importance_no"]))
async def process_event_importance(callback: CallbackQuery, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        is_important = callback.data == "importance_yes"
        data = await state.get_data()
        event_name = data.get("event_name")
        event_date = data.get("date")
        description = data.get("description")
        subject = data.get("subject")
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if user and user.group_membership:
            await group_repo.create_event(
                group_id=user.group_membership.group.id,
                created_by_user_id=user.telegram_id,
                title=event_name,
                description=description,
                subject=subject,
                date=event_date,
                is_important=is_important
            )
            await state.clear()
            await callback.message.delete()
            await callback.message.answer(f"Событие «{event_name}» на {event_date.strftime('%Y-%m-%d')} создано! {'[Важное]' if is_important else ''}")
        else:
            await callback.message.answer("Ошибка: вы не состоите в группе.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в process_event_importance: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()
        await message.answer("Произошла ошибка при создании приглашения. Попробуйте позже.")
