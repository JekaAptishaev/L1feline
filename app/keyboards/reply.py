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
            [KeyboardButton(text="➕ Создать событие")],  # Новая кнопка
            [KeyboardButton(text="📅 Показать календарь")]  # Новая кнопка
        ],
        resize_keyboard=True
    )

def get_calendar_keyboard(events) -> InlineKeyboardMarkup:
    """Возвращает инлайн-клавиатуру с календарем событий."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    current_month = datetime.now().month
    current_year = datetime.now().year

    for event in events or []:
        date = datetime.strptime(event.date, "%Y-%m-%d").date()
        button_text = f"{date.day} - {event.name}"
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"event_{event.id}")])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    return keyboard
