import re
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.repository import UserRepo, GroupRepo
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.db.models import User, Event, TopicList, Topic, TopicSelection, Queue, QueueParticipant
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
logger = logging.getLogger(__name__)

class SelectMonth(StatesGroup):
    waiting_for_month = State()

class BookingInteraction(StatesGroup):
    selecting_topic = State()
    selecting_queue_position = State()

def get_month_weeks_keyboard(month: str) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру с выбором недель для указанного месяца."""
    year, month = map(int, month.split("-"))
    weeks = [
        ("1 неделя (1-7)", f"week_1_{year}_{month}"),
        ("2 неделя (8-14)", f"week_2_{year}_{month}"),
        ("3 неделя (15-21)", f"week_3_{year}_{month}"),
        ("4 неделя (22-28/30/31)", f"week_4_{year}_{month}"),
    ]
    inline_keyboard = [
        [InlineKeyboardButton(text=text, callback_data=data)] for text, data in weeks
    ] + [[InlineKeyboardButton(text="Выбрать месяц", callback_data="select_month")]]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_week_days_keyboard(days_with_events, week_num: int, month: int, year: int) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру с днями недели и кнопкой 'Назад к неделям'."""
    inline_keyboard = [
        [InlineKeyboardButton(text=str(day), callback_data=f"day_{day}_{month}_{year}")] for day in days_with_events
    ]
    inline_keyboard.append([InlineKeyboardButton(text="Назад к неделям", callback_data=f"month_back_{year}_{month}")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

async def get_day_events_keyboard(events, day: int, month: int, year: int, week_num: int, week_events: list, group_repo: GroupRepo) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру с кнопками для событий дня и навигацией."""
    inline_keyboard = []
    for event in events:
        # Проверяем наличие списка тем или очереди
        topic_list = await group_repo.get_topic_list_by_event(event.id)
        queue = await group_repo.get_queue_by_event(event.id)
        booking_label = ""
        if topic_list:
            booking_label = "[Темы]"
        elif queue:
            booking_label = "[Очередь]"
        button_text = f"{event.title} {booking_label}{' [Важное]' if event.is_important else ''}"
        inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"event_{event.id}")])

    # Вычисляем границы текущей недели
    start_week_day = (week_num - 1) * 7 + 1
    last_day_of_month = (datetime(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31
    end_week_day = min(start_week_day + 6, last_day_of_month)

    # Находим дни с событиями в текущей неделе
    event_days = sorted(set(event.date.day for event in week_events if event.date.month == month and event.date.year == year))

    # Находим ближайший предыдущий и следующий день с событиями
    current_date = datetime(year, month, day).date()
    prev_event_day = None
    next_event_day = None

    for event_day in event_days:
        event_date = datetime(year, month, event_day).date()
        if event_date < current_date and event_day >= start_week_day:
            prev_event_day = event_day
        if event_date > current_date and event_day <= end_week_day and (next_event_day is None or event_day < next_event_day):
            next_event_day = event_day

    # Создаем кнопки навигации
    nav_buttons = []
    if prev_event_day:
        prev_date = datetime(year, month, prev_event_day)
        nav_buttons.append(
            InlineKeyboardButton(
                text="Предыдущий день",
                callback_data=f"day_{prev_date.day}_{prev_date.month}_{prev_date.year}"
            )
        )
    else:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⏹ Раньше нет событий",
                callback_data="no_events_earlier"
            )
        )

    if next_event_day:
        next_date = datetime(year, month, next_event_day)
        nav_buttons.append(
            InlineKeyboardButton(
                text="Следующий день",
                callback_data=f"day_{next_date.day}_{next_date.month}_{next_date.year}"
            )
        )
    else:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⏹ Дальше нет событий",
                callback_data="no_events_later"
            )
        )

    inline_keyboard.append(nav_buttons)
    inline_keyboard.append(
        [InlineKeyboardButton(text="Назад к выбору дня", callback_data=f"week_back_{week_num}_{year}_{month}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_day_back_button(day: int, month: int, year: int, week_num: int) -> InlineKeyboardMarkup:
    """Генерирует кнопки возврата к списку событий дня и неделям."""
    inline_keyboard = [
        [InlineKeyboardButton(text="Назад к дню", callback_data=f"day_back_{day}_{month}_{year}")],
        [InlineKeyboardButton(text="Назад к выбору дня", callback_data=f"week_back_{week_num}_{year}_{month}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_cancel_button(year: int, month: int) -> InlineKeyboardMarkup:
    """Генерирует кнопку отмены для возврата к неделям."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=f"month_back_{year}_{month}")]
    ])

@router.message(F.text == "📅 Показать календарь")
async def show_calendar(message: Message, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    """Обработчик команды 'Показать календарь'."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            return

        current_month = datetime.now().strftime("%Y-%m")
        await state.update_data(current_month=current_month)
        keyboard = get_month_weeks_keyboard(current_month)
        await message.answer(f"Выберите неделю для {current_month}:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в show_calendar: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("week_") & ~F.data.startswith("week_back_"))
async def handle_week_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    """Обработчик выбора недели."""
    try:
        logger.info(f"handle_week_selection called with callback.data: {callback.data}")
        _, week_num, year, month = callback.data.split("_")
        year, month, week_num = int(year), int(month), int(week_num)
        start_day = (week_num - 1) * 7 + 1
        end_day = start_day + 6
        if week_num == 4:
            end_day = min(end_day, (datetime(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31)

        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        week_events = [
            event for event in events
            if start_day <= event.date.day <= end_day and event.date.month == month and event.date.year == year
        ]

        keyboard = get_week_days_keyboard([], week_num, month, year)  # Пустой список дней для кнопки "Назад"
        if not week_events:
            await callback.message.edit_text(
                "Нет событий на этой неделе. Вернитесь к выбору месяца.",
                reply_markup=keyboard
            )
            await callback.answer()
            return

        days_with_events = sorted(set(event.date.day for event in week_events))
        keyboard = get_week_days_keyboard(days_with_events, week_num, month, year)
        await callback.message.edit_text(f"Дни с событиями на {week_num}-й неделе:", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_week_selection: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("day_") & ~F.data.startswith("day_back_"))
async def handle_day_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик выбора дня."""
    try:
        logger.info(f"handle_day_selection called with callback.data: {callback.data}")
        _, day, month, year = callback.data.split("_")
        day, month, year = int(day), int(month), int(year)
        event_date = datetime(year, month, day).date()
        week_num = ((day - 1) // 7) + 1

        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        day_events = [event for event in events if event.date == event_date]

        if not day_events:
            await callback.message.edit_text("Нет событий на этот день.")
            await callback.answer()
            return

        # Фильтруем события текущей недели
        start_day = (week_num - 1) * 7 + 1
        end_day = min(start_day + 6, (datetime(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31)
        week_events = [
            event for event in events
            if start_day <= event.date.day <= end_day and event.date.month == month and event.date.year == year
        ]

        keyboard = await get_day_events_keyboard(day_events, day, month, year, week_num, week_events, group_repo)
        await callback.message.edit_text(
            f"События на {event_date.strftime('%Y-%m-%d')}:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_day_selection: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("event_"))
async def handle_event_details(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик для отображения деталей события."""
    try:
        logger.info(f"handle_event_details called with callback.data: {callback.data}")
        event_id = callback.data.replace("event_", "")
        event = await group_repo.get_event_by_id(event_id)
        if not event:
            await callback.message.edit_text("Событие не найдено.")
            await callback.answer()
            return

        user = await user_repo.get_user_with_group_info(callback.from_user.id)
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

        # Кнопка возврата к дню
        week_num = ((event.date.day - 1) // 7) + 1
        keyboard.button(text="Назад к дню", callback_data=f"day_back_{event.date.day}_{event.date.month}_{event.date.year}")
        await callback.message.edit_text(details, reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_event_details: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("select_topic_"))
async def handle_topic_selection(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик для выбора темы."""
    try:
        event_id = callback.data.replace("select_topic_", "")
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
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
            if len(selections) < topic_list.max_participants_per_topic:
                keyboard.button(text=f"{topic.title} ({len(selections)}/{topic_list.max_participants_per_topic})", callback_data=f"topic_{topic.id}")
        keyboard.button(text="Отмена", callback_data=f"event_{event_id}")
        await state.set_state(BookingInteraction.selecting_topic)
        await state.update_data(event_id=event_id)
        await callback.message.edit_text("Выберите тему:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_topic_selection: {e}")
        await state.clear()
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("topic_"))
async def process_topic_selection(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик подтверждения выбора темы."""
    try:
        topic_id = callback.data.replace("topic_", "")
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
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
        logger.error(f"Ошибка в process_topic_selection: {e}")
        await state.clear()
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("select_queue_"))
async def handle_queue_selection(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    """Обработчик для выбора места в очереди."""
    try:
        event_id = callback.data.replace("select_queue_", "")
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
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
        logger.error(f"Ошибка в handle_queue_selection: {e}")
        await state.clear()
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("day_back_"))
async def handle_day_back(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик возврата к списку событий дня."""
    try:
        logger.info(f"handle_day_back called with callback.data: {callback.data}")
        _, _, day, month, year = callback.data.split("_")
        day, month, year = int(day), int(month), int(year)
        event_date = datetime(year, month, day).date()
        week_num = ((day - 1) // 7) + 1

        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        day_events = [event for event in events if event.date == event_date]

        if not day_events:
            await callback.message.edit_text("Нет событий на этот день.")
            await callback.answer()
            return

        # Фильтруем события текущей недели
        start_day = (week_num - 1) * 7 + 1
        end_day = min(start_day + 6, (datetime(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31)
        week_events = [
            event for event in events
            if start_day <= event.date.day <= end_day and event.date.month == month and event.date.year == year
        ]

        keyboard = await get_day_events_keyboard(day_events, day, month, year, week_num, week_events, group_repo)
        await callback.message.edit_text(
            f"События на {event_date.strftime('%Y-%m-%d')}:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_day_back: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "no_events_earlier")
async def handle_no_events_earlier(callback: CallbackQuery):
    """Обработчик для кнопки, когда нет событий раньше."""
    await callback.answer("На этой неделе нет событий, запланированных на более ранние дни.", show_alert=True)

@router.callback_query(F.data == "no_events_later")
async def handle_no_events_later(callback: CallbackQuery):
    """Обработчик для кнопки, когда нет событий позже."""
    await callback.answer("Далее на этой неделе нет дней с событиями.", show_alert=True)

@router.callback_query(F.data.startswith("week_back_"))
async def handle_week_back(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    """Обработчик возврата к списку дней недели."""
    try:
        logger.info(f"handle_week_back called with callback.data: {callback.data}")
        parts = callback.data.split('_')
        week_num = int(parts[2])
        year = int(parts[3])
        month = int(parts[4])

        start_day = (week_num - 1) * 7 + 1
        end_day = start_day + 6
        if week_num == 4:
            end_day = min(end_day, (datetime(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31)

        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        week_events = [
            event for event in events
            if start_day <= event.date.day <= end_day and event.date.month == month and event.date.year == year
        ]

        keyboard = get_week_days_keyboard([], week_num, month, year)
        if not week_events:
            await callback.message.edit_text(
                "Нет событий на этой неделе. Вернитесь к выбору месяца.",
                reply_markup=keyboard
            )
            await callback.answer()
            return

        days_with_events = sorted(set(event.date.day for event in week_events))
        keyboard = get_week_days_keyboard(days_with_events, week_num, month, year)
        await callback.message.edit_text(f"Дни с событиями на {week_num}-й неделе:", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_week_back: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("month_back_"))
async def handle_month_back(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата к выбору месяца."""
    try:
        logger.info(f"handle_month_back called with callback.data: {callback.data}")
        parts = callback.data.split('_')
        year = int(parts[-2])
        month = int(parts[-1])

        selected_month = f"{year}-{month:02d}"
        await state.update_data(current_month=selected_month)
        keyboard = get_month_weeks_keyboard(selected_month)
        await callback.message.edit_text(f"Выберите неделю для {selected_month}:", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_month_back: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "select_month")
async def start_select_month(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала выбора месяца."""
    try:
        logger.info(f"start_select_month called with callback.data: {callback.data}")
        data = await state.get_data()
        current_month = data.get("current_month", datetime.now().strftime("%Y-%m"))
        year, month = map(int, current_month.split("-"))
        await state.set_state(SelectMonth.waiting_for_month)
        keyboard = get_cancel_button(year, month)
        await callback.message.edit_text(
            "Введите месяц в формате YYYY-MM, YYYY MM или YYYYMM (например, 2025-07, 2025 07, 202507). "
            "Для текущего года введите просто номер месяца (например, 7).",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_select_month: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.message(SelectMonth.waiting_for_month)
async def process_month_input(message: Message, state: FSMContext):
    """Обработчик ввода месяца."""
    try:
        input_text = message.text.strip()
        current_year = datetime.now().year
        if len(input_text) in (1, 2) and input_text.isdigit():
            month = int(input_text)
            if 1 <= month <= 12:
                selected_month = f"{current_year}-{month:02d}"
            else:
                raise ValueError("Месяц должен быть от 1 до 12.")
        elif len(input_text) == 7 and input_text[4] in ('-', ' '):
            year, month = input_text.split(input_text[4])
            selected_month = f"{int(year)}-{int(month):02d}"
        elif len(input_text) == 6 and input_text.isdigit():
            year = int(input_text[:4])
            month = int(input_text[4:6])
            if 1 <= month <= 12:
                selected_month = f"{year}-{month:02d}"
            else:
                raise ValueError("Месяц должен быть от 1 до 12.")
        else:
            raise ValueError("Неверный формат.")

        await state.update_data(current_month=selected_month)
        keyboard = get_month_weeks_keyboard(selected_month)
        await message.answer(f"Выберите неделю для {selected_month}:", reply_markup=keyboard)
        await state.clear()
    except ValueError as ve:
        await message.answer(f"Ошибка: {str(ve)} Попробуйте снова.")
    except Exception as e:
        logger.error(f"Ошибка в process_month_input: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")