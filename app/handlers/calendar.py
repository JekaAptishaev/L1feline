import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from datetime import datetime, timedelta
from app.db.repository import UserRepo, GroupRepo

router = Router()
logger = logging.getLogger(__name__)

class SelectWeek(StatesGroup):
    waiting_for_week = State()

class SelectMonth(StatesGroup):
    waiting_for_month = State()

# Словарь для русских названий месяцев
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

# Словарь для русских названий дней недели
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
    """Возвращает даты начала и конца недели с учетом смещения."""
    if base_date is None:
        base_date = datetime.now().date()
    start_of_week = base_date - timedelta(days=base_date.weekday())  # Понедельник
    start_of_week += timedelta(weeks=offset)  # Смещение
    end_of_week = start_of_week + timedelta(days=6)  # Воскресенье
    return start_of_week, end_of_week

def format_week_label(start_date):
    """Форматирует метку недели, например, '2-8 Сентябрь'."""
    end_date = start_date + timedelta(days=6)
    start_day = start_date.strftime("%d").lstrip("0")  # Убираем ведущий ноль
    end_day = end_date.strftime("%d").lstrip("0")
    start_month = MONTHS_RU[start_date.month]
    month_name = start_month
    if start_date.month != end_date.month:
        end_month = MONTHS_RU[end_date.month]
        month_name = f"{start_month}-{end_month}"
    return f"{start_day}-{end_day} {month_name}"

def get_weekly_calendar_keyboard(events, start_of_week, show_week_selection=False, week_offset=0):
    """Генерирует клавиатуру для недельного календаря."""
    inline_keyboard = []
    
    # Кнопки для событий
    if events and not show_week_selection:
        for event in sorted(events, key=lambda e: e.date):
            day = event.date.strftime("%d").lstrip("0")
            weekday = WEEKDAYS_RU[event.date.weekday()]
            button_text = f"{day} {weekday}: {event.title} {'[Важное]' if event.is_important else ''}"
            inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"event_{event.id}")])
    
    # Кнопки навигации
    if not show_week_selection:
        nav_buttons = [
            InlineKeyboardButton(text="Выбрать неделю", callback_data="select_week"),
            InlineKeyboardButton(text="Прошлая", callback_data=f"week_{week_offset-1}"),
            InlineKeyboardButton(text="Следующая", callback_data=f"week_{week_offset+1}")
        ]
        inline_keyboard.append(nav_buttons)
    else:
        # Кнопки выбора недели
        for i in range(-1, 2):
            week_start, _ = get_week_dates(week_offset + i)
            label = format_week_label(week_start)
            inline_keyboard.append([InlineKeyboardButton(text=label, callback_data=f"week_{week_offset+i}")])
        # Кнопки "Назад" и "Вперёд"
        inline_keyboard.append([
            InlineKeyboardButton(text="Назад", callback_data=f"shift_weeks_{week_offset-1}"),
            InlineKeyboardButton(text="Вперёд", callback_data=f"shift_weeks_{week_offset+1}")
        ])
        # Кнопка "Выбрать месяц"
        inline_keyboard.append([InlineKeyboardButton(text="Выбрать месяц", callback_data="select_month")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_month_selection_keyboard():
    """Генерирует клавиатуру с 12 месяцами."""
    inline_keyboard = []
    months = list(MONTHS_RU.items())
    for i in range(0, 12, 3):
        row = [
            InlineKeyboardButton(text=month_name, callback_data=f"month_{month_num}")
            for month_num, month_name in months[i:i+3]
        ]
        inline_keyboard.append(row)
    inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="select_week")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_event_back_button():
    """Генерирует кнопку возврата к недельному календарю."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад к неделе", callback_data="week_0")]
    ])

@router.message(F.text == "📅 Показать календарь")
async def show_calendar(message: Message, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    """Обработчик команды 'Показать календарь' для отображения недельного календаря."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            return

        group = user.group_membership.group
        start_of_week, end_of_week = get_week_dates()  # Текущая неделя
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
        await state.update_data(week_offset=0, current_year=datetime.now().year)  # Сохраняем текущий год
    except Exception as e:
        logger.error(f"Ошибка в show_calendar: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("week_"))
async def handle_week_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    """Обработчик выбора недели."""
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
    """Обработчик начала выбора недели."""
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
    """Обработчик начала выбора месяца."""
    try:
        data = await state.get_data()
        current_year = data.get("current_year", datetime.now().year)
        keyboard = get_month_selection_keyboard()
        await callback.message.edit_text(
            f"Выберите месяц для {current_year} года:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_select_month: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("month_"))
async def handle_month_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    """Обработчик выбора месяца."""
    try:
        month = int(callback.data.split("_")[1])
        data = await state.get_data()
        current_year = data.get("current_year", datetime.now().year)
        
        # Вычисляем смещение недели так, чтобы 1-е число месяца попало в первую неделю
        first_day = datetime(current_year, month, 1).date()
        week_start = first_day - timedelta(days=first_day.weekday())  # Понедельник той недели
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        offset = (week_start - current_week_start).days // 7  # Смещение относительно текущей недели

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
    """Обработчик смещения списка недель."""
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
async def handle_event_details(callback: CallbackQuery, group_repo: GroupRepo):
    """Обработчик для отображения деталей события."""
    try:
        event_id = callback.data.replace("event_", "")
        event = await group_repo.get_event_by_id(event_id)
        if event:
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
            keyboard = get_event_back_button()
            await callback.message.edit_text(details, reply_markup=keyboard)
        else:
            await callback.message.edit_text("Событие не найдено.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_event_details: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)