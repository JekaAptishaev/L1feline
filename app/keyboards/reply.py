from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

def get_main_menu_unregistered() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для незарегистрированных пользователей."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Создать группу")],
            [KeyboardButton(text="🔗 Присоединиться по ссылке")]
        ],
        resize_keyboard=True
    )

def get_main_menu_leader() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для старосты группы."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 События и Бронь")],
            [KeyboardButton(text="👥 Участники группы")],
            [KeyboardButton(text="⚙️ Настройки группы")],
            [KeyboardButton(text="➕ Создать событие")],
            [KeyboardButton(text="📅 Показать календарь")],
            [KeyboardButton(text="📅 Показать недельный календарь")],
            [KeyboardButton(text="🔗 Создать приглашение")]
        ],
        resize_keyboard=True
    )

def get_assistant_menu() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для ассистента группы."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Управление событиями")],
            [KeyboardButton(text="📅 Показать календарь")],
            [KeyboardButton(text="📅 Показать недельный календарь")]
        ],
        resize_keyboard=True
    )

def get_regular_member_menu() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для обычных участников группы."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Участники группы")],
            [KeyboardButton(text="📅 Показать календарь")],
            [KeyboardButton(text="📅 Показать недельный календарь")]
        ],
        resize_keyboard=True
    )

def get_calendar_keyboard(events) -> InlineKeyboardMarkup:
    """Возвращает инлайн-клавиатуру с календарем событий для текущего месяца."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    current_month = datetime.now().month
    current_year = datetime.now().year

    if not events:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Нет событий", callback_data="none")])
    else:
        for event in events:
            if event.date.month == current_month and event.date.year == current_year:
                button_text = f"{event.date.day} - {event.title} {'[В]' if event.is_important else ''}"
                keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"event_{event.id}")])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    return keyboard

def get_weekly_calendar_keyboard(events, start_of_week: datetime.date) -> InlineKeyboardMarkup:
    """Возвращает инлайн-клавиатуру с календарем событий для указанной недели."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    end_of_week = start_of_week + timedelta(days=6)

    # Фильтрация событий за неделю
    week_events = [e for e in events if start_of_week <= e.date <= end_of_week]
    if not week_events:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Нет событий на этой неделе", callback_data="none")])
    else:
        for event in sorted(week_events, key=lambda e: e.date):
            button_text = f"{event.date.strftime('%a, %d %b')} - {event.title} {'[В]' if event.is_important else ''}"
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"event_{event.id}")])

    # Кнопки навигации по неделям
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Пред. неделя", callback_data=f"week_{-1}"),
        InlineKeyboardButton(text="Текущая неделя", callback_data="week_0"),
        InlineKeyboardButton(text="След. неделя ➡️", callback_data="week_1")
    ])
    return keyboard

def get_weekly_calendar_back_button() -> InlineKeyboardMarkup:
    """Возвращает кнопку возврата к недельному календарю."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к календарю", callback_data="week_back")]
    ])