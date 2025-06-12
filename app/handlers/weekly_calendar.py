import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_weekly_calendar_keyboard, get_weekly_calendar_back_button
from app.db.models import User, TopicList, Topic, TopicSelection, Queue, QueueParticipant

router = Router()
logger = logging.getLogger(__name__)

class BookingInteraction(StatesGroup):
    selecting_topic = State()
    selecting_queue_position = State()

@router.message(Command("weekly_calendar"))
@router.message(F.text == "📅 Показать недельный календарь")
async def show_weekly_calendar(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик команды /weekly_calendar и кнопки для отображения календаря по неделям."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.reply("Вы не состоите в группе.")
            return

        group = user.group_membership.group
        # Текущая неделя начинается с понедельника
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        events = await group_repo.get_group_events(group.id)
        logger.info(f"Events retrieved for weekly calendar: {[event.date for event in events]}")
        calendar = get_weekly_calendar_keyboard(events, start_of_week)
        await message.reply(
            f"Календарь событий группы «{group.name}» (неделя с {start_of_week.strftime('%Y-%m-%d')}):",
            reply_markup=calendar
        )
    except Exception as e:
        logger.error(f"Ошибка в show_weekly_calendar: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("week_"))
async def handle_week_navigation(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик переключения недель."""
    try:
        user = await user_repo.get_user_with_group_info(callback.from_id)
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
        logger.error(f"Ошибка в handle_week_navigation: {e}", exc_info=True)
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("event_"))
async def handle_event_details(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик для отображения деталей события."""
    try:
        event_id = callback.data.replace("event_", "")
        event = await group_repo.get_event_by_id(event_id)
        if not event:
            await callback.message.edit_text("Событие не найдено.")
            await callback.answer()
            return

        user = await user_repo.get_user_with_group_info(callback.from_id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

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

        # Проверяем списки тем или очередь
        topic_list = await group_repo.get_topic_list_by_event(event.id)
        queue = await group_repo.get_queue_by_event(event.id)

        keyboard = InlineKeyboardBuilder()
        if topic_list:
            topics = await group_repo.get_topics_by_topic_list(topic_list.id)
            details += f"\nСписок тем ({len(topics)}):\n"
            for topic in topics:
                selections = await group_repo.get_topic_selections(topic.id)
                details += f"- {topic.title} ({len(selections)}/{topic_list.max_participants_per_topic})\n"
            if not user.group_membership.is_leader and not user.group_membership.is_assistant:
                keyboard.button(text="Выбрать тему", callback_data=f"select_topic_{event.id}")
        if queue:
            participants = await group_repo.get_queue_participants(queue.id)
            details += f"\nОчередь ({len(participants)}/{queue.max_participants or '∞'}):\n"
            for participant in participants:
                participant_user = await user_repo.get_user_with_group_info(participant.user_id)
                details += f"{participant.position}. {participant_user.first_name} {participant_user.last_name or ''}\n"
            if not user.group_membership.is_leader and not user.group_membership.is_assistant:
                keyboard.button(text="Занять место", callback_data=f"select_queue_{event.id}")

        # Кнопки управления для старост и ассистентов
        if user.group_membership.is_leader or user.group_membership.is_assistant:
            keyboard.button(text="Редактировать", callback_data=f"edit_event_{event.id}")
            keyboard.button(text="Удалить", callback_data=f"delete_event_{event.id}")

        # Кнопка возврата к календарю
        keyboard.button(text="Назад к календарю", callback_data="week_back")
        await callback.message.edit_text(details, reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_event_details: {e}", exc_info=True)
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "week_back")
async def handle_week_back(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик возврата к календарю."""
    try:
        user = await user.get_user_with_group_info(callback.from_id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        events = await group_repo.get_group_events(group.id)
        calendar = get_weekly_calendar(events, start_of_week)
        await callback.message.edit_text(
            f"Календарь событий группы «{group.name}» (неделя с {start_of_week.strftime('%Y-%m-%d')}):",
            reply_markup=calendar
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_week_back: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("select_topic_"))
async def handle_topic_selection(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик для выбора темы."""
    try:
        event_id = callback.data.replace("select_topic_", "")
        user = await user_repo.get_user_with_group_info(callback.from_id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        topic_list = await group_repo.get_topic_list_by_event(event_id)
        if not topic_list:
            await callback.message.edit_text("Список тем не найден.")
            await callback.answer()
            return

        topics = await group_repo.get_topics_by_topic_list(topic_list.id)
        if not topics:
            await callback.message.edit_text("Тем нет.")
            await callback.answer()
            return

        keyboard = InlineKeyboardBuilder()
        for topic in topics:
            selections = await group_repo.get_topic_selections(topic.id)
            topic_selections
            if len(selections) < topic_list.max_participants_per_topic:
                keyboard.button(text=f"{topic.title} ({len(selections)}/{topic_list.max_participants_per_topic})", callback_data=f"topic_{{topic.id}}")
        keyboard.button(text="Отмена", callback_data=f"event_{event_id}")
        await state.set_state(BookingInteraction.selecting_topic)
        await state.update_data(event_id=event_id)
        await callback.message.edit_text("Выберите тему:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_topic_selection: {e}", exc_info=True)
        await state.clear()
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("topic_"))
async def process_topic_selection(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик подтверждения выбора темы."""
    try:
        topic_id = callback.data.replace("topic_", "")
        user = await user_repo.get_user_with_group_info(callback.from_id)
        data = await state.get_data()
        event_id = data.get("event_id")

        topic_list = await group_repo.get_topic_list_by_event(event_id)
        selections = await group_repo.get_topic_selections(topic_id)
        if len(selections) >= topic_list.max_participants_per_topic:
            await callback.message.edit_text("Эта тема уже заполнена.")
            await state.clear()
            await callback.answer()
            return

        await group_repo.create_topic_selection(
            topic_id=topic_id,
            user_id=user.telegram_id
        )
        topics = await group_repo.get_topics_by_topic_list(topic_list.id)
        topic = next(t for t in topics if t.id == topic_id)
        await state.clear()
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Назад", callback_data=f"event_{event_id}")
        await callback.message.edit_text(f"Вы выбрали тему: {topic.title}", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в process_topic_selection: {e}", exc_info=True)
        await state.clear()
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("select_queue_"))
async def handle_queue_selection(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик для выбора места в очереди."""
    try:
        event_id = callback.data.replace("select_queue_", "")
        user = await user_repo.get_user_with_group_info(callback.from_id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        queue = await group_repo.get_queue_by_event(event_id)
        if not queue:
            await callback.message.edit_text("Очередь не найдена.")
            await callback.answer()
            return

        participants = await group_repo.get_queue_participants(queue.id)
        if queue.max_participants and len(participants) >= queue.max_participants:
            await callback.message.edit_text("Очередь заполнена.")
            await callback.answer()
            return

        # Находим следующую свободную позицию
        taken_positions = {p.position for p in participants}
        next_position = 1
        while next_position in taken_positions:
            next_position += 1

        await group_repo.create_queue_participant(
            queue_id=queue.id,
            user_id=user.telegram_id,
            position=next_position
        )
        await state.clear()
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Назад", callback_data=f"event_{event_id}")
        await callback.message.edit_text(f"Вы заняли место #{next_position} в очереди.", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_queue_selection: {e}", exc_info=True)
        await state.clear()
        await callback.answer("Произошла ошибка.", show_alert=True)