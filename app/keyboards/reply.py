from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_unregistered() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Создать группу")],
            [KeyboardButton(text="🔗 Присоединиться по ключу")]
        ],
        resize_keyboard=True
    )

def get_main_menu_leader() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Участники группы*")],
            [KeyboardButton(text="➕ Создать событие")],
            [KeyboardButton(text="📅 Показать календарь")],
            [KeyboardButton(text="🔗 Создать приглашение")],
            [KeyboardButton(text="🗑 Удалить группу")]
        ],
        resize_keyboard=True
    )

def get_assistant_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Участники группы")],
            [KeyboardButton(text="➕ Создать событие")],
            [KeyboardButton(text="📅 Показать календарь")],
            [KeyboardButton(text="🚪 Выйти из группы")]
        ],
        resize_keyboard=True
    )

def get_regular_member_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Участники группы")],
            [KeyboardButton(text="📅 Показать календарь")],
            [KeyboardButton(text="🚪 Выйти из группы")]
        ],
        resize_keyboard=True
    )

def get_event_details_keyboard(event_id: str, has_queue: bool, is_in_queue: bool, show_view_queue: bool = True) -> InlineKeyboardMarkup:
    inline_keyboard = []
    if has_queue:
        queue_buttons = []
        if is_in_queue:
            queue_buttons.append(InlineKeyboardButton(text="Отказаться от места", callback_data=f"leave_queue_{event_id}"))
        else:
            queue_buttons.append(InlineKeyboardButton(text="Записаться в очередь", callback_data=f"join_queue_{event_id}"))
        if show_view_queue:
            queue_buttons.append(InlineKeyboardButton(text="Посмотреть очередь", callback_data=f"view_queue_{event_id}"))
        inline_keyboard.append(queue_buttons)
    inline_keyboard.append([InlineKeyboardButton(text="Назад к неделе", callback_data="week_0")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)