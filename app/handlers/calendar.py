import re
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.repository import UserRepo, GroupRepo
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import selectinload
from app.db.models import User

router = Router()
logger = logging.getLogger(__name__)

class SelectMonth(StatesGroup):
    waiting_for_month = State()

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

def get_day_events_keyboard(events, day: int, month: int, year: int) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру с кнопками для событий дня и навигацией."""
    inline_keyboard = [
        [InlineKeyboardButton(text=f"{event.title} {'[Важное]' if event.is_important else ''}", callback_data=f"event_{event.id}")]
        for event in events
    ]
    prev_day = datetime(year, month, day) - timedelta(days=1)
    next_day = datetime(year, month, day) + timedelta(days=1)
    inline_keyboard.append([
        InlineKeyboardButton(text="Предыдущий день", callback_data=f"day_{prev_day.day}_{prev_day.month}_{prev_day.year}"),
        InlineKeyboardButton(text="Следующий день", callback_data=f"day_{next_day.day}_{next_day.month}_{next_day.year}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_day_back_button(day: int, month: int, year: int) -> InlineKeyboardMarkup:
    """Генерирует кнопку возврата к списку событий дня."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад к дню", callback_data=f"day_back_{day}_{month}_{year}")]
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

@router.callback_query(F.data.startswith("week_"))
async def handle_week_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
    """Обработчик выбора недели."""
    try:
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

        if not week_events:
            await callback.message.edit_text("Нет событий на этой неделе.")
            await callback.answer()
            return

        days_with_events = sorted(set(event.date.day for event in week_events))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(day), callback_data=f"day_{day}_{month}_{year}")] for day in days_with_events
        ])
        await callback.message.edit_text(f"Дни с событиями на {week_num}-й неделе:", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_week_selection: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)


@router.callback_query(F.data.regexp(r"^day_(\d+)_(\d+)_(\d+)$"))  # Измененный фильтр
async def handle_day_selection(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        # Разбор данных через регулярное выражение
        match = re.match(r"day_(\d+)_(\d+)_(\d+)$", callback.data)
        if not match:
            await callback.answer("Неверный формат данных.")
            return

        day, month, year = map(int, match.groups())
        event_date = datetime(year, month, day).date()

        # Остальной код без изменений...
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

        keyboard = get_day_events_keyboard(day_events, day, month, year)
        await callback.message.edit_text(
            f"События на {event_date.strftime('%Y-%m-%d')}:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_day_selection: {e}")
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
            keyboard = get_day_back_button(event.date.day, event.date.month, event.date.year)
            await callback.message.edit_text(details, reply_markup=keyboard)
        else:
            await callback.message.edit_text("Событие не найдено.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_event_details: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("day_back_"))
async def handle_day_back(callback: CallbackQuery, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик возврата к списку событий дня."""
    try:
        _, _, day, month, year = callback.data.split("_")
        day, month, year = int(day), int(month), int(year)
        event_date = datetime(year, month, day).date()

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

        keyboard = get_day_events_keyboard(day_events, day, month, year)
        await callback.message.edit_text(
            f"События на {event_date.strftime('%Y-%m-%d')}:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в handle_day_back: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data == "select_month")
async def start_select_month(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала выбора месяца."""
    try:
        await state.set_state(SelectMonth.waiting_for_month)
        await callback.message.edit_text(
            "Введите месяц в формате YYYY-MM, YYYY MM или YYYYMM (например, 2025-07, 2025 07, 202507). "
            "Для текущего года введите просто номер месяца (например, 7)."
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