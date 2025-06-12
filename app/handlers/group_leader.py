import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_main_menu_leader
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

class DeleteMember(StatesGroup):
    waiting_for_member_number = State()

class ManageBookings(StatesGroup):
    waiting_for_event_number = State()
    waiting_for_booking_type = State()
    waiting_for_booking_entry_number = State()

class AssignAssistant(StatesGroup):
    waiting_for_member_number = State()

class CreateEvent(StatesGroup):
    waiting_for_event_name = State()
    waiting_for_event_date = State()
    waiting_for_description = State()
    waiting_for_subject = State()
    waiting_for_importance = State()
    waiting_for_booking_type = State()
    waiting_for_topic_list_details = State()
    waiting_for_queue_max_participants = State()

@router.message(F.text == "➕ Создать событие/бронь")
async def start_create_event(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        logger.info(f"Received command 'Создать событие/бронь' from user_id={message.from_user.id}")
        current_state = await state.get_state()
        if current_state:
            logger.warning(f"User {message.from_user.id} is in state {current_state}. Clearing state.")
            await state.clear()
            await message.reply("Предыдущее действие отменено.")

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        logger.debug(f"User data: {user}, membership: {user.group_membership if user else None}")
        if not user or not user.group_membership or not user.group_membership.is_leader:
            logger.error(f"User {message.from_user.id} has no rights to create events.")
            await message.reply("У вас нет доступа к созданию событий.")
            return

        await state.set_state(CreateEvent.waiting_for_event_name)
        await state.update_data(is_booking_required=False)  # Для события с возможностью "Без брони"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await message.reply("Введите название задачи:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in start_create_event for user_id {message.from_user.id}: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при создании задачи. Попробуйте снова.")

@router.message(F.text == "➕ Создать бронь")
async def start_create_booking(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        logger.info(f"Received command 'Создать бронь' from user_id={message.from_user.id}")
        current_state = await state.get_state()
        if current_state:
            logger.warning(f"User {message.from_user.id} is in state {current_state}. Clearing state.")
            await state.clear()
            await message.reply("Предыдущее действие отменено.")

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        logger.debug(f"User data: {user}, membership: {user.group_membership if user else None}")
        if not user or not user.group_membership or not user.group_membership.is_leader:
            logger.error(f"User {message.from_user.id} has no rights to create bookings.")
            await message.reply("У вас нет доступа к созданию брони.")
            return

        await state.set_state(CreateEvent.waiting_for_event_name)
        await state.update_data(is_booking_required=True)  # Для события с обязательной бронью
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await message.reply("Введите название задачи:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in start_create_booking for user_id {message.from_user.id}: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при создании брони. Попробуйте снова.")

@router.callback_query(F.data == "cancel_event_creation")
async def cancel_event_creation(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info(f"Canceling event creation for user {callback.from_user.id}")
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Создание задачи отменено.", reply_markup=get_main_menu_leader())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cancel_event_creation: {e}", exc_info=True)
        await callback.message.answer("Ошибка при отмене. Попробуйте снова.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_event_name)
async def process_event_name(message: Message, state: FSMContext):
    try:
        logger.info(f"Processing event name from user {message.from_user.id}: {message.text}")
        event_name = message.text.strip()
        if len(event_name) < 3 or len(event_name) > 100:
            await message.reply("Название задачи должно содержать от 3 до 100 символов.")
            return

        await state.update_data(event_name=event_name)
        await state.set_state(CreateEvent.waiting_for_event_date)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await message.reply("Введите дату задачи (например, 2025-06-15):", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in process_event_name: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при вводе названия. Попробуйте снова.")

@router.message(CreateEvent.waiting_for_event_date)
async def process_event_date(message: Message, state: FSMContext):
    try:
        logger.info(f"Processing event date from user {message.from_user.id}: {message.text}")
        event_date = message.text.strip()
        try:
            # Проверяем формат, но сохраняем как строку
            datetime.strptime(event_date, '%Y-%m-%d')
        except ValueError:
            await message.reply("Неверный формат даты. Используйте ГГГГ-ММ-ДД (например, 2025-07-06).")
            return

        # Сохраняем дату как строку
        await state.update_data(date=event_date)
        await state.set_state(CreateEvent.waiting_for_description)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Пропустить", callback_data="skip_description")
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await message.reply("Введите описание задачи:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in process_event_date: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при вводе даты. Попробуйте снова.")

@router.callback_query(F.data == "skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info(f"Skipping description for user {callback.from_user.id}")
        await state.update_data(description=None)
        await state.set_state(CreateEvent.waiting_for_subject)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Пропустить", callback_data="skip_subject")
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await callback.message.edit_text("Введите тему задачи:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in skip_description: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Ошибка при пропуске описания. Попробуйте снова.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    try:
        logger.info(f"Processing event description from user {message.from_user.id}: {message.text}")
        description = message.text.strip()
        await state.update_data(description=description)
        await state.set_state(CreateEvent.waiting_for_subject)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Пропустить", callback_data="skip_subject")
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await message.reply("Введите тему задачи:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in process_event_description: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при вводе описания. Попробуйте снова.")

@router.callback_query(F.data == "skip_subject")
async def skip_subject(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info(f"Skipping subject for user {callback.from_user.id}")
        await state.update_data(subject=None)
        await state.set_state(CreateEvent.waiting_for_importance)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Да", callback_data="importance_yes")
        keyboard.button(text="Нет", callback_data="importance_no")
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await callback.message.edit_text("Является ли задача важной?", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in skip_subject: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Ошибка при пропуске темы. Попробуйте снова.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_subject)
async def process_event_subject(message: Message, state: FSMContext):
    try:
        logger.info(f"Processing event subject from user {message.from_user.id}: {message.text}")
        subject = message.text.strip()
        await state.update_data(subject=subject)
        await state.set_state(CreateEvent.waiting_for_importance)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Да", callback_data="importance_yes")
        keyboard.button(text="Нет", callback_data="importance_no")
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await message.reply("Является ли задача важной?", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in process_event_subject: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при вводе темы. Попробуйте снова.")

@router.callback_query(F.data.in_(["importance_yes", "importance_no"]))
async def process_event_importance(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info(f"Processing event importance for user {callback.from_user.id}: {callback.data}")
        is_important = callback.data == "importance_yes"
        await state.update_data(is_important=is_important)
        await state.set_state(CreateEvent.waiting_for_booking_type)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Список тем", callback_data="booking_topic_list")
        keyboard.button(text="Очередь", callback_data="booking_queue")
        data = await state.get_data()
        if not data.get("is_booking_required", False):
            keyboard.button(text="Без брони", callback_data="booking_none")
        message_text = "Выберите тип брони для задачи (список тем или очередь):" if data.get("is_booking_required", False) else "Выберите тип брони для задачи:"
        await callback.message.edit_text(message_text, reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_event_importance: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Ошибка при выборе важности. Попробуйте снова.")
        await callback.answer()

@router.callback_query(F.data == "booking_none")
async def process_booking_none(callback: CallbackQuery, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        logger.info(f"Processing no booking for user {callback.from_user.id}")
        data = await state.get_data()
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        event = await group_repo.create_event(
            group_id=user.group_membership.group.id,
            created_by_user_id=user.telegram_id,
            title=data.get("event_name"),
            description=data.get("description"),
            subject=data.get("subject"),
            date=data.get("date"),
            is_important=data.get("is_important")
        )
        await state.clear()
        await callback.message.delete()
        await callback.message.answer(
            f"Задача «{event.title}» на {event.date.strftime('%Y-%m-%d')} создана! {'[Важная]' if event.is_important else ''}",
            reply_markup=get_main_menu_leader()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_booking_none: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Ошибка при создании задачи. Попробуйте снова.")
        await callback.answer()

@router.callback_query(F.data == "booking_topic_list")
async def start_topic_list_creation(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info(f"Starting topic list creation for user {callback.from_user.id}")
        await state.set_state(CreateEvent.waiting_for_topic_list_details)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await callback.message.edit_text(
            "Введите максимальное число участников на одну тему (число) и список тем через запятые (например: 3, Тема 1, Тема 2):",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_topic_list_creation: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Ошибка при создании списка тем. Попробуйте снова.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_topic_list_details)
async def process_topic_list_details(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        logger.info(f"Processing topic list details from user {message.from_user.id}: {message.text}")
        input_text = message.text.strip()
        parts = [p.strip() for p in input_text.split(",")]
        if len(parts) < 2:
            await message.reply("Укажите максимальное число участников и хотя бы одну тему (например: 3, Тема 1, Тема 2).")
            return

        try:
            max_participants = int(parts[0])
            if max_participants < 1:
                await message.reply("Максимальное число участников должно быть больше 0.")
                return
        except ValueError:
            await message.reply("Первое значение должно быть числом (максимальное число участников).")
            return

        topics = parts[1:]
        if not all(t for t in topics):
            await message.reply("Все темы должны быть непустыми.")
            return

        data = await state.get_data()
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.reply("Вы не состоите в группе.")
            return

        # Преобразуем строку обратно в дату
        try:
            date_obj = datetime.strptime(data["date"], '%Y-%m-%d').date()
        except (KeyError, ValueError) as e:
            logger.error(f"Ошибка преобразования даты: {e}")
            await message.reply("Ошибка в формате даты. Начните заново.")
            await state.clear()
            return

        event = await group_repo.create_event(
            group_id=user.group_membership.group.id,
            created_by_user_id=user.telegram_id,
            title=data.get("event_name"),
            description=data.get("description"),
            subject=data.get("subject"),
            date=date_obj,  # Используем объект date
            is_important=data.get("is_important")
        )

        topic_list_title = f"Список тем для {data.get('event_name')}"
        topic_list = await group_repo.create_topic_list(
            event_id=event.id,
            title=topic_list_title,
            created_by_user_id=user.telegram_id,
            max_participants_per_topic=max_participants
        )

        for topic_title in topics:
            await group_repo.create_topic(
                topic_list_id=topic_list.id,
                title=topic_title
            )

        await state.clear()
        await message.reply(
            f"Задача «{event.title}» на {event.date.strftime('%Y-%m-%d')} создана с бронированием (список тем)! {'[Важная]' if event.is_important else ''}",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Error in process_topic_list_details: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при создании списка тем. Попробуйте снова.")

@router.callback_query(F.data == "booking_queue")
async def start_queue_creation(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info(f"Starting queue creation for user {callback.from_user.id}")
        await state.set_state(CreateEvent.waiting_for_queue_max_participants)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Без ограничения", callback_data="queue_no_limit")
        keyboard.button(text="Отмена", callback_data="cancel_event_creation")
        await callback.message.edit_text(
            "Введите максимальное число участников в очереди (число) или выберите 'Без ограничения':",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_queue_creation: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Ошибка при создании очереди. Попробуйте снова.")
        await callback.answer()

@router.callback_query(F.data == "queue_no_limit")
async def process_queue_no_limit(callback: CallbackQuery, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        logger.info(f"Processing queue with no limit for user {callback.from_user.id}")
        data = await state.get_data()
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        event = await group_repo.create_event(
            group_id=user.group_membership.group.id,
            created_by_user_id=user.telegram_id,
            title=data.get("event_name"),
            description=data.get("description"),
            subject=data.get("subject"),
            date=data.get("date"),
            is_important=data.get("is_important")
        )

        queue_title = f"Очередь для {data.get('event_name')}"
        await group_repo.create_queue(
            event_id=event.id,
            title=queue_title,
            max_participants=None
        )

        await state.clear()
        await callback.message.delete()
        await callback.message.answer(
            f"Задача «{event.title}» на {event.date.strftime('%Y-%m-%d')} создана с бронированием (очередь без ограничения)! {'[Важная]' if event.is_important else ''}",
            reply_markup=get_main_menu_leader()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_queue_no_limit: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Ошибка при создании очереди. Попробуйте снова.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_queue_max_participants)
async def process_queue_max_participants(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        logger.info(f"Processing queue max participants from user {message.from_user.id}: {message.text}")
        input_text = message.text.strip()
        try:
            max_participants = int(input_text)
            if max_participants < 1:
                await message.reply("Максимальное число участников должно быть больше 0.")
                return
        except ValueError:
            await message.reply("Введите число (максимальное число участников).")
            return

        data = await state.get_data()
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.reply("Вы не состоите в группе.")
            return

        event = await group_repo.create_event(
            group_id=user.group_membership.group.id,
            created_by_user_id=user.telegram_id,
            title=data.get("event_name"),
            description=data.get("description"),
            subject=data.get("subject"),
            date=data["date"],
            is_important=data.get("is_important")
        )

        queue_title = f"Очередь для {data.get('event_name')}"
        await group_repo.create_queue(
            event_id=event.id,
            title=queue_title,
            max_participants=max_participants
        )

        await state.clear()
        await message.reply(
            f"Задача «{event.title}» на {event.date.strftime('%Y-%m-%d')} создана с бронированием (очередь, до {max_participants} участников)! {'[Важная]' if event.is_important else ''}",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Error in process_queue_max_participants: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при создании очереди. Попробуйте снова.")

@router.message(F.text == "👥 Участники группы")
async def handle_group_members(message: Message, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        current_state = await state.get_state()
        if current_state:
            await message.reply("Сначала завершите текущую операцию.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.reply("У вас нет прав для просмотра участников группы.")
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await message.reply("В группе пока нет участников.")
            return

        member_list = []
        for idx, member in enumerate(members, 1):
            member_user = await user_repo.get_user_with_group_info(member.user_id)
            if member_user:
                role = "Староста" if member.is_leader else "Ассистент" if member.is_assistant else "Участник"
                member_info = f"{idx}. {member_user.first_name} {member_user.last_name or ''} (@{member_user.telegram_username or 'без имени'}) - {role}"
                member_list.append(member_info)

        response = f"Участники группы «{group.name}»:\n" + "\n".join(member_list)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Удалить участника", callback_data="delete_member")
        keyboard.button(text="Назначить ассистента", callback_data="assign_assistant")
        await message.reply(response, reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in handle_group_members: {e}", exc_info=True)
        await message.reply("Произошла ошибка при получении списка участников. Попробуйте позже.")

@router.callback_query(F.data == "delete_member")
async def start_delete_member(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await callback.message.reply("У вас нет прав для удаления участников.")
            await callback.answer()
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await callback.message.reply("В группе пока нет участников.")
            await callback.answer()
            return

        await state.update_data(members=members, group_id=group.id)
        await state.set_state(DeleteMember.waiting_for_member_number)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_delete_member")
        await callback.message.reply("Введите номер участника, которого желаете удалить:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_delete_member: {e}", exc_info=True)
        await state.clear()
        await callback.message.reply("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "cancel_delete_member")
async def cancel_delete_member(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await callback.message.reply("Удаление участника отменено.", reply_markup=get_main_menu_leader())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cancel_delete_member: {e}", exc_info=True)
        await state.clear()
        await callback.message.reply("Произошла ошибка при отмене. Попробуйте позже.")
        await callback.answer()

@router.message(DeleteMember.waiting_for_member_number)
async def process_delete_member(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        data = await state.get_data()
        members = data.get("members")
        group_id = data.get("group_id")
        if not members or not group_id:
            await message.reply("Ошибка: данные об участниках или группе отсутствуют.")
            await state.clear()
            return

        try:
            member_number = int(message.text.strip())
            if member_number < 1 or member_number > len(members):
                await message.reply("Неверный номер участника. Попробуйте снова.")
                return
        except ValueError:
            await message.reply("Введите корректный номер участника (число).")
            return

        member_to_delete = members[member_number - 1]
        member_user = await user_repo.get_user_with_group_info(member_to_delete.user_id)
        if not member_user:
            await message.reply("Ошибка: пользователь не найден.")
            await state.clear()
            return

        if member_user.telegram_id == message.from_user.id:
            await message.reply("Вы не можете удалить самого себя из группы.")
            await state.clear()
            return

        events = await group_repo.get_group_events(group_id)
        for event in events:
            topic_list = await group_repo.get_topic_list_by_event(event.id)
            queue = await group_repo.get_queue_by_event(event.id)
            if topic_list:
                topics = await group_repo.get_topics_by_topic_list(topic_list.id)
                for topic in topics:
                    await group_repo.delete_topic_selection(topic_id=topic.id, user_id=member_user.telegram_id)
            if queue:
                await group_repo.delete_queue_participant(queue_id=queue.id, user_id=member_user.telegram_id)

        await group_repo.delete_member(group_id=group_id, user_id=member_to_delete.user_id)
        await state.clear()
        await message.reply(
            f"Участник {member_user.first_name} {member_user.last_name or ''} удалён из группы.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Error in process_delete_member: {e}", exc_info=True)
        await state.clear()
        await message.reply("Произошла ошибка при удалении участника. Попробуйте позже.")

@router.callback_query(F.data == "assign_assistant")
async def start_assign_assistant(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await callback.message.reply("У вас нет прав для назначения ассистентов.")
            await callback.answer()
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await callback.message.reply("В группе пока нет участников.")
            await callback.answer()
            return

        await state.update_data(members=members, group_id=group.id)
        await state.set_state(AssignAssistant.waiting_for_member_number)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_assign_assistant")
        await callback.message.reply("Введите номер участника, которого хотите назначить ассистентом:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_assign_assistant: {e}", exc_info=True)
        await state.clear()
        await callback.message.reply("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "cancel_assign_assistant")
async def cancel_assign_assistant(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await callback.message.reply("Назначение ассистента отменено.", reply_markup=get_main_menu_leader())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cancel_assign_assistant: {e}", exc_info=True)
        await state.clear()
        await callback.message.reply("Произошла ошибка при отмене. Попробуйте снова.")
        await callback.answer()

@router.message(AssignAssistant.waiting_for_member_number)
async def process_assign_assistant(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        data = await state.get_data()
        members = data.get("members")
        group_id = data.get("group_id")
        if not members or not group_id:
            await message.reply("Ошибка: данные об участниках или группе отсутствуют.")
            await state.clear()
            return

        try:
            member_number = int(message.text.strip())
            if member_number < 1 or member_number > len(members):
                await message.reply("Неверный номер участника. Попробуйте снова.")
                return
        except ValueError:
            await message.reply("Введите корректный номер участника (число).")
            return

        member_to_assign = members[member_number - 1]
        member_user = await user_repo.get_user_with_group_info(member_to_assign.user_id)
        if not member_user:
            await message.reply("Ошибка: пользователь не найден.")
            await state.clear()
            return

        if member_to_assign.is_leader:
            await message.reply("Староста не может быть ассистентом.")
            await state.clear()
            return

        if member_to_assign.is_assistant:
            await message.reply(f"{member_user.first_name} {member_user.last_name or ''} уже является ассистентом.")
            await state.clear()
            return

        await group_repo.update_member_role(group_id=group_id, user_id=member_user.telegram_id, is_assistant=True)
        await state.clear()
        await message.reply(
            f"{member_user.first_name} {member_user.last_name or ''} назначен(а) ассистентом группы.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Error in process_assign_assistant: {e}", exc_info=True)
        await state.clear()
        await message.reply("Произошла ошибка при назначении ассистента. Попробуйте позже.")

@router.message(F.text == "🔗 Создать приглашение")
async def create_invite(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.reply("У вас нет прав для создания ключей доступа.")
            return

        group = user.group_membership.group
        invite_token = await group_repo.create_invite(group.id, user.telegram_id)
        await state.clear()
        await message.reply(
            f"Ключ доступа создан!\n\nКлюч: {invite_token}\nПередайте этот ключ пользователям для присоединения к группе «{group.name}»."
        )
    except Exception as e:
        logger.error(f"Error in create_invite: {e}", exc_info=True)
        await state.clear()
        await message.reply("Произошла ошибка при создании ключа доступа. Попробуйте позже.")

@router.message(F.text == "📋 Управление бронированиями")
async def handle_manage_bookings(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        current_state = await state.get_state()
        if current_state:
            await message.reply("Сначала завершите текущую операцию.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.reply("У вас нет прав для управления бронированиями.")
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        if not events:
            await message.reply("В группе пока нет событий.")
            return

        event_list = []
        for idx, event in enumerate(events, 1):
            topic_list = await group_repo.get_topic_list_by_event(event.id)
            queue = await group_repo.get_queue_by_event(event.id)
            booking_label = "[Темы]" if topic_list else "[Очередь]" if queue else ""
            event_info = f"{idx}. {event.title} ({event.date.strftime('%Y-%m-%d')}) {booking_label}"
            event_list.append(event_info)

        response = f"События группы «{group.name}» с бронированиями:\n" + "\n".join(event_list)
        await state.update_data(events=events)
        await state.set_state(ManageBookings.waiting_for_event_number)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_manage_bookings")
        await message.reply(response + "\n\nВведите номер события для управления бронированиями:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in handle_manage_bookings: {e}", exc_info=True)
        await state.clear()
        await message.reply("Произошла ошибка при получении списка событий. Попробуйте позже.")

@router.callback_query(F.data == "cancel_manage_bookings")
async def cancel_manage_bookings(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await callback.message.reply("Управление бронированиями отменено.", reply_markup=get_main_menu_leader())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cancel_manage_bookings: {e}", exc_info=True)
        await state.clear()
        await callback.message.reply("Произошла ошибка при отмене. Попробуйте позже.")
        await callback.answer()

@router.message(ManageBookings.waiting_for_event_number)
async def process_event_selection(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        data = await state.get_data()
        events = data.get("events")
        if not events:
            await message.reply("Ошибка: данные о событиях отсутствуют.")
            await state.clear()
            return

        try:
            event_number = int(message.text.strip())
            if event_number < 1 or event_number > len(events):
                await message.reply("Неверный номер события. Попробуйте снова.")
                return
        except ValueError:
            await message.reply("Введите корректный номер события (число).")
            return

        event = events[event_number - 1]
        await state.update_data(selected_event=event)
        topic_list = await group_repo.get_topic_list_by_event(event.id)
        queue = await group_repo.get_queue_by_event(event.id)

        if not topic_list and not queue:
            await message.reply("У этого события нет бронирований.")
            await state.clear()
            return

        keyboard = InlineKeyboardBuilder()
        if topic_list:
            keyboard.button(text="Список тем", callback_data="booking_type_topic_list")
        if queue:
            keyboard.button(text="Очередь", callback_data="booking_type_queue")
        keyboard.button(text="Отмена", callback_data="cancel_manage_bookings")
        await state.set_state(ManageBookings.waiting_for_booking_type)
        await message.reply("Выберите тип бронирования:", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Error in process_event_selection: {e}", exc_info=True)
        await state.clear()
        await message.reply("Произошла ошибка при выборе события. Попробуйте позже.")

@router.callback_query(F.data.startswith("booking_type_"))
async def process_booking_type(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        booking_type = callback.data.replace("booking_type_", "")
        data = await state.get_data()
        event = data.get("selected_event")
        if not event:
            await callback.message.reply("Ошибка: событие не выбрано.")
            await state.clear()
            await callback.answer()
            return

        booking_list = []
        if booking_type == "topic_list":
            topic_list = await group_repo.get_topic_list_by_event(event.id)
            if topic_list:
                topics = await group_repo.get_topics_by_topic_list(topic_list.id)
                for topic in topics:
                    selections = await group_repo.get_topic_selections(topic.id)
                    for idx, selection in enumerate(selections, 1):
                        user = await user_repo.get_user_with_group_info(selection.user_id)
                        booking_list.append(
                            f"{idx}. {topic.title} - {user.first_name} {user.last_name or ''} (@{user.telegram_username or 'без имени'})"
                        )
                await state.update_data(booking_entries=selections, booking_id=topic_list.id, entry_type="topic")
        elif booking_type == "queue":
            queue = await group_repo.get_queue_by_event(event.id)
            if queue:
                participants = await group_repo.get_queue_participants(queue.id)
                for idx, participant in enumerate(participants, 1):
                    user = await user_repo.get_user_with_group_info(participant.user_id)
                    booking_list.append(
                        f"{idx}. Место #{participant.position} - {user.first_name} {user.last_name or ''} (@{user.telegram_username or 'без имени'})"
                    )
                await state.update_data(booking_entries=participants, booking_id=queue.id, entry_type="queue")

        if not booking_list:
            await callback.message.reply("Нет бронирований для этого типа.")
            await state.clear()
            await callback.answer()
            return

        response = f"Бронирования для события «{event.title}» ({booking_type}):\n" + "\n".join(booking_list)
        await state.set_state(ManageBookings.waiting_for_booking_entry_number)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_manage_bookings")
        await callback.message.reply(response + "\n\nВведите номер бронирования для удаления:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_booking_type: {e}", exc_info=True)
        await state.clear()
        await callback.message.reply("Произошла ошибка при выборе типа бронирования. Попробуйте позже.")
        await callback.answer()

@router.message(ManageBookings.waiting_for_booking_entry_number)
async def process_booking_entry_deletion(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        data = await state.get_data()
        entries = data.get("booking_entries")
        booking_id = data.get("booking_id")
        entry_type = data.get("entry_type")
        event = data.get("selected_event")
        if not entries or not booking_id or not entry_type or not event:
            await message.reply("Ошибка: данные о бронировании отсутствуют.")
            await state.clear()
            return

        try:
            entry_number = int(message.text.strip())
            if entry_number < 1 or entry_number > len(entries):
                await message.reply("Неверный номер бронирования. Попробуйте снова.")
                return
        except ValueError:
            await message.reply("Введите корректный номер бронирования (число).")
            return

        entry = entries[entry_number - 1]
        user = await user_repo.get_user_with_group_info(entry.user_id)
        if not user:
            await message.reply("Ошибка: пользователь не найден.")
            await state.clear()
            return

        if entry_type == "topic":
            await group_repo.delete_topic_selection(topic_id=entry.topic_id, user_id=entry.user_id)
            booking_info = f"темы для события «{event.title}»"
        else:  # queue
            await group_repo.delete_queue_participant(queue_id=booking_id, user_id=entry.user_id)
            booking_info = f"очереди для события «{event.title}»"

        await state.clear()
        await message.reply(
            f"Бронирование удалено: {user.first_name} {user.last_name or ''} из {booking_info}.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Error in process_booking_entry_deletion: {e}", exc_info=True)
        await state.clear()
        await message.reply("Произошла ошибка при удалении бронирования. Попробуйте позже.")