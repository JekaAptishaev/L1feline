import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from datetime import datetime, timedelta
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_event_details_keyboard

router = Router()
logger = logging.getLogger(__name__)

class SelectWeek(StatesGroup):
    waiting_for_week = State()

class SelectMonth(StatesGroup):
    waiting_for_month = State()

MONTHS_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь"
}

WEEKDAYS_RU = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

def get_week_dates(offset=0, base_date=None):
    if base_date is None:
        base_date = datetime.now().date()
    start_of_week = base_date - timedelta(days=base_date.weekday())
    start_of_week += timedelta(weeks=offset)
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week

def format_week_label(start_date):
    end_date = start_date + timedelta(days=6)
    start_day = start_date.strftime("%d").lstrip("0")
    end_day = end_date.strftime("%d").lstrip("0")
    start_month = MONTHS_RU[start_date.month]
    month_name = start_month
    if start_date.month != end_date.month:
        end_month = MONTHS_RU[end_date.month]
        month_name = f"{start_month}-{end_month}"
    return f"{start_day}-{end_day} {month_name}"

def get_weekly_calendar_keyboard(events, start_of_week, show_week_selection=False, week_offset=0):
    inline_keyboard = []
    
    if events and not show_week_selection:
        for event in sorted(events, key=lambda e: e.date):
            day = event.date.strftime("%d").lstrip("0")
            weekday = WEEKDAYS_RU[event.date.weekday()]
            button_text = f"{day} {weekday}: {event.title} {'[Важное]' if event.is_important else ''}"
            inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"event_{event.id}")])
    
    if not show_week_selection:
        nav_buttons = [
            InlineKeyboardButton(text="Выбрать неделю", callback_data="select_week"),
            InlineKeyboardButton(text="Прошлая", callback_data=f"week_{week_offset-1}"),
            InlineKeyboardButton(text="Следующая", callback_data=f"week_{week_offset+1}")
        ]
        inline_keyboard.append(nav_buttons)
    else:
        for i in range(-1, 2):
            week_start, _ = get_week_dates(week_offset + i)
            label = format_week_label(week_start)
            inline_keyboard.append([InlineKeyboardButton(text=label, callback_data=f"week_{week_offset+i}")])
        inline_keyboard.append([
            InlineKeyboardButton(text="Назад", callback_data=f"shift_weeks_{week_offset-1}"),
            InlineKeyboardButton(text="Вперёд", callback_data=f"shift_weeks_{week_offset+1}")
        ])
        inline_keyboard.append([InlineKeyboardButton(text="Выбрать месяц", callback_data="select_month")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_month_selection_keyboard(current_year):
    inline_keyboard = []
    months = list(MONTHS_RU.items())
    for i in range(0, 12, 3):
        row = [
            InlineKeyboardButton(text=month_name, callback_data=f"month_{month_num}")
            for month_num, month_name in months[i:i+3]
        ]
        inline_keyboard.append(row)
    inline_keyboard.append([InlineKeyboardButton(text="К месяцу", callback_data="select_week")])
    inline_keyboard.append([
        InlineKeyboardButton(text="Назад", callback_data="shift_year_-1"),
        InlineKeyboardButton(text="Вперёд", callback_data="shift_year_1")
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

@router.message(F.text == "📅 Показать календарь")
async def show_calendar(message: Message, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            return

        group = user.group_membership.group
        start_of_week, end_of_week = get_week_dates()
        events = await group_repo.get_group_events(group.id)
        week_events = [event for event in events if start_of_week <= event.date <= end_of_week]
        
        start_day = start_of_week.strftime("%d").lstrip("0")
        start_month = MONTHS_RU[start_of_week.month]
        end_day = end_of_week.strftime("%d").lstrip("0")
        end_month = MONTHS_RU[end_of_week.month]
        keyboard = get_weekly_calendar_keyboard(week_events, start_of_week)
        await message.answer(
            f"Неделя с {start_day} {start_month} по {end_day} {end_month}",
            reply_markup=keyboard
        )
        await state.update_data(week_offset=0, current_year=datetime.now().year)
    except Exception as e:
        logger.error(f"Ошибка в show_calendar: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("week_"))
async def handle_week_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        offset = int(callback.data.split("_")[1])
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        start_of_week, end_of_week = get_week_dates(offset)
        events = await group_repo.get_group_events(group.id)
        week_events = [event for event in events if start_of_week <= event.date <= end_of_week]
        
        start_day = start_of_week.strftime("%d").lstrip("0")
        start_month = MONTHS_RU[start_of_week.month]
        end_day = end_of_week.strftime("%d").lstrip("0")
        end_month = MONTHS_RU[end_of_week.month]
        keyboard = get_weekly_calendar_keyboard(week_events, start_of_week, week_offset=offset)
        await callback.message.edit_text(
            f"Неделя с {start_day} {start_month} по {end_day} {end_month}",
            reply_markup=keyboard
        )
        await state.update_data(week_offset=offset)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_week_selection: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "select_week")
async def start_select_week(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        data = await state.get_data()
        week_offset = data.get("week_offset", 0)
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        start_of_week, _ = get_week_dates(week_offset)
        keyboard = get_weekly_calendar_keyboard([], start_of_week, show_week_selection=True, week_offset=week_offset)
        await callback.message.edit_text(
            f"Выберите неделю для группы «{group.name}»:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_select_week: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "select_month")
async def start_select_month(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        current_year = data.get("current_year", datetime.now().year)
        keyboard = get_month_selection_keyboard(current_year)
        await callback.message.edit_text(
            f"Выберите месяц для {current_year} года:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_select_month: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("shift_year_"))
async def handle_year_shift(callback: CallbackQuery, state: FSMContext):
    try:
        year_offset = int(callback.data.split("_")[2])
        data = await state.get_data()
        current_year = data.get("current_year", datetime.now().year)
        new_year = current_year + year_offset
        keyboard = get_month_selection_keyboard(new_year)
        await callback.message.edit_text(
            f"Выберите месяц для {new_year} года:",
            reply_markup=keyboard
        )
        await state.update_data(current_year=new_year)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_year_shift: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("month_"))
async def handle_month_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        month = int(callback.data.split("_")[1])
        data = await state.get_data()
        current_year = data.get("current_year", datetime.now().year)
        
        first_day = datetime(current_year, month, 1).date()
        week_start = first_day - timedelta(days=first_day.weekday())
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        offset = (week_start - current_week_start).days // 7

        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        start_of_week, end_of_week = get_week_dates(offset)
        events = await group_repo.get_group_events(group.id)
        week_events = [event for event in events if start_of_week <= event.date <= end_of_week]
        
        start_day = start_of_week.strftime("%d").lstrip("0")
        start_month = MONTHS_RU[start_of_week.month]
        end_day = end_of_week.strftime("%d").lstrip("0")
        end_month = MONTHS_RU[end_of_week.month]
        keyboard = get_weekly_calendar_keyboard(week_events, start_of_week, week_offset=offset)
        await callback.message.edit_text(
            f"Неделя с {start_day} {start_month} по {end_day} {end_month}",
            reply_markup=keyboard
        )
        await state.update_data(week_offset=offset, current_year=current_year)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_month_selection: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("shift_weeks_"))
async def handle_shift_weeks(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        new_offset = int(callback.data.split("_")[2])
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        group = user.group_membership.group
        start_of_week, _ = get_week_dates(new_offset)
        keyboard = get_weekly_calendar_keyboard([], start_of_week, show_week_selection=True, week_offset=new_offset)
        await callback.message.edit_text(
            f"Выберите неделю для группы «{group.name}»:",
            reply_markup=keyboard
        )
        await state.update_data(week_offset=new_offset)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_shift_weeks: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("event_"))
async def handle_event_details(callback: CallbackQuery, group_repo: GroupRepo, user_repo: UserRepo, state: FSMContext):
    try:
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

        queue_data = await user_repo.get_queue_entries(event_id)
        has_queue = bool(queue_data and "max_slots" in queue_data)
        is_in_queue = False
        if has_queue:
            for position, queued_user_id in queue_data["entries"].items():
                if int(queued_user_id) == callback.from_user.id:
                    is_in_queue = True
                    break

        data = await state.get_data()
        show_view_queue = data.get(f"show_view_queue_{event_id}", True)

        # Проверяем, является ли пользователь старостой или ассистентом
        can_delete = user.group_membership.is_leader or user.group_membership.is_assistant

        day = event.date.strftime("%d").lstrip("0")
        month = MONTHS_RU[event.date.month]
        year = event.date.strftime("%Y")
        details = (
            f"Детали события:\n"
            f"Название: {event.title}\n"
            f"Дата: {day} {month} {year}\n"
        )
        if event.description:
            details += f"Описание: {event.description}\n"
        if event.subject:
            details += f"Тема: {event.subject}\n"
        details += f"{'[Важное]' if event.is_important else ''}"
        if has_queue:
            details += f"\nОчередь: {len(queue_data.get('entries', {}))}/{queue_data['max_slots']} мест занято"

        keyboard = get_event_details_keyboard(event_id, has_queue, is_in_queue, show_view_queue, can_delete=can_delete)
        await callback.message.edit_text(details, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_event_details: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("join_queue_"))
async def join_queue(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        event_id = callback.data.replace("join_queue_", "")
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        success, message, is_in_queue = await user_repo.join_queue(event_id, user.telegram_id)
        event = await group_repo.get_event_by_id(event_id)
        if not event:
            await callback.message.edit_text("Событие не найдено.")
            await callback.answer()
            return

        queue_data = await user_repo.get_queue_entries(event_id)
        has_queue = bool(queue_data and "max_slots" in queue_data)

        data = await state.get_data()
        show_view_queue = data.get(f"show_view_queue_{event_id}", True)

        # Проверяем, является ли пользователь старостой или ассистентом
        can_delete = user.group_membership.is_leader or user.group_membership.is_assistant

        day = event.date.strftime("%d").lstrip("0")
        month = MONTHS_RU[event.date.month]
        year = event.date.strftime("%Y")
        details = (
            f"Детали события:\n"
            f"Название: {event.title}\n"
            f"Дата: {day} {month} {year}\n"
        )
        if event.description:
            details += f"Описание: {event.description}\n"
        if event.subject:
            details += f"Тема: {event.subject}\n"
        details += f"{'[Важное]' if event.is_important else ''}"
        if has_queue:
            details += f"\nОчередь: {len(queue_data.get('entries', {}))}/{queue_data['max_slots']} мест занято"

        keyboard = get_event_details_keyboard(event_id, has_queue, is_in_queue or success, show_view_queue, can_delete=can_delete)
        await callback.message.edit_text(details, reply_markup=keyboard)
        await callback.answer(message, show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в join_queue: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("leave_queue_"))
async def leave_queue(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        event_id = callback.data.replace("leave_queue_", "")
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await callback.answer()
            return

        success, message = await user_repo.leave_queue(event_id, user.telegram_id)
        event = await group_repo.get_event_by_id(event_id)
        if not event:
            await callback.message.edit_text("Событие не найдено.")
            await callback.answer()
            return

        queue_data = await user_repo.get_queue_entries(event_id)
        has_queue = bool(queue_data and "max_slots" in queue_data)
        is_in_queue = False

        # Сбрасываем состояние show_view_queue для данного события
        await state.update_data(**{f"show_view_queue_{event_id}": True})
        show_view_queue = True

        # Проверяем, является ли пользователь старостой или ассистентом
        can_delete = user.group_membership.is_leader or user.group_membership.is_assistant

        day = event.date.strftime("%d").lstrip("0")
        month = MONTHS_RU[event.date.month]
        year = event.date.strftime("%Y")
        details = (
            f"Детали события:\n"
            f"Название: {event.title}\n"
            f"Дата: {day} {month} {year}\n"
        )
        if event.description:
            details += f"Описание: {event.description}\n"
        if event.subject:
            details += f"Тема: {event.subject}\n"
        details += f"{'[Важное]' if event.is_important else ''}"
        if has_queue:
            details += f"\nОчередь: {len(queue_data.get('entries', {}))}/{queue_data['max_slots']} мест занято"

        keyboard = get_event_details_keyboard(event_id, has_queue, is_in_queue, show_view_queue, can_delete=can_delete)
        await callback.message.edit_text(details, reply_markup=keyboard)
        await callback.answer(message, show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в leave_queue: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("view_queue_"))
async def view_queue(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        event_id = callback.data.replace("view_queue_", "")
        event = await group_repo.get_event_by_id(event_id)
        if not event:
            await callback.message.edit_text("Событие не найдено.")
            await callback.answer()
            return

        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership or str(user.group_membership.group.id) != str(event.group_id):
            await callback.message.edit_text("У вас нет доступа к этой очереди.")
            await callback.answer()
            return

        queue_data = await user_repo.get_queue_entries(event_id)
        if not queue_data or "entries" not in queue_data:
            await callback.message.edit_text("Очередь для этого события не создана.")
            await callback.answer()
            return

        entries = queue_data["entries"]
        max_slots = queue_data["max_slots"]
        response = f"Очередь для события «{event.title}» ({len(entries)}/{max_slots} мест занято):\n"

        sorted_entries = sorted(entries.items(), key=lambda x: int(x[0]))
        for position, user_id in sorted_entries:
            user_info = await user_repo.get_user_with_group_info(int(user_id))
            if user_info:
                full_name = f"{user_info.last_name or ''} {user_info.first_name} {user_info.middle_name or ''}".strip()
                response += f"{position}. {full_name} (@{user_info.telegram_username or 'без имени'})\n"
            else:
                response += f"{position}. Неизвестный пользователь (ID: {user_id})\n"

        if not entries:
            response += "Очередь пуста."

        is_in_queue = False
        for position, queued_user_id in entries.items():
            if int(queued_user_id) == callback.from_user.id:
                is_in_queue = True
                break

        # Проверяем, является ли пользователь старостой или ассистентом
        can_delete = user.group_membership.is_leader or user.group_membership.is_assistant

        await state.update_data(**{f"show_view_queue_{event_id}": False})
        await callback.message.edit_text(
            response,
            reply_markup=get_event_details_keyboard(event_id, True, is_in_queue, show_view_queue=False, can_delete=can_delete)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в view_queue: {e}")
        await callback.message.edit_text("Произошла ошибка при просмотре очереди.")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("delete_event_"))
async def delete_event(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    try:
        event_id = callback.data.replace("delete_event_", "")
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

        # Проверяем, является ли пользователь старостой или ассистентом
        if not (user.group_membership.is_leader or user.group_membership.is_assistant):
            await callback.message.edit_text("У вас нет прав для удаления события.")
            await callback.answer()
            return

        # Удаляем событие
        await group_repo.delete_event(event_id)

        # Возвращаем пользователя к календарю
        data = await state.get_data()
        week_offset = data.get("week_offset", 0)
        group = user.group_membership.group
        start_of_week, end_of_week = get_week_dates(week_offset)
        events = await group_repo.get_group_events(group.id)
        week_events = [event for event in events if start_of_week <= event.date <= end_of_week]
        
        start_day = start_of_week.strftime("%d").lstrip("0")
        start_month = MONTHS_RU[start_of_week.month]
        end_day = end_of_week.strftime("%d").lstrip("0")
        end_month = MONTHS_RU[end_of_week.month]
        keyboard = get_weekly_calendar_keyboard(week_events, start_of_week, week_offset=week_offset)
        await callback.message.edit_text(
            f"Событие «{event.title}» удалено.\nНеделя с {start_day} {start_month} по {end_day} {end_month}",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в delete_event: {e}")
        await callback.answer("Произошла ошибка при удалении события.", show_alert=True)