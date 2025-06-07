from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

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
            [KeyboardButton(text="🔗 Создать приглашение")]
        ],
        resize_keyboard=True
    )

def get_assistant_menu() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для ассистента группы."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Управление событиями")],
            [KeyboardButton(text="📅 Показать календарь")]
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
            date = datetime.strptime(event.date, "%Y-%m-%d").date()
            # Фильтрация по текущему месяцу
            if date.month == current_month and date.year == current_year:
                button_text = f"{date.day} - {event.title} {'[В]' if event.is_important else ''}"
                keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"event_{event.id}")])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    return keyboard
