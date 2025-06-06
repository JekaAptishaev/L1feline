from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

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
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# Пример добавления другой клавиатуры (опционально)
def get_settings_menu() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для настроек группы."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 Изменить название")],
            [KeyboardButton(text="📩 Пригласить участников")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )