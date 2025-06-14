import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import UserRepo, GroupRepo
from datetime import datetime, timedelta
from app.keyboards.reply import get_assistant_menu, get_main_menu_leader, get_main_menu_unregistered
from uuid import uuid4
from app.db.models import TopicList, Topic

router = Router()
logger = logging.getLogger(__name__)

class CreateEvent(StatesGroup):
    main_menu = State()
    waiting_for_subject = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_date = State()
    waiting_for_importance = State()
    waiting_for_topics_and_queues = State()
    waiting_for_queue_slots = State()

# Словарь для перевода месяцев на русский
MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

# Словарь для перевода дней недели на русский
DAYS_RU = {
    0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
}

def format_date_ru(date: datetime, today: datetime = None) -> str:
    """Форматирует дату на русском языке."""
    if today and date.date() == today.date():
        return "Сегодня"
    return f"{date.day} {DAYS_RU[date.weekday()]} {MONTHS_RU[date.month]}"

def format_date_with_day_ru(date: datetime) -> str:
    """Форматирует дату с днём недели на русском языке."""
    day_name = DAYS_RU[date.weekday()]
    return f"{date.day} {day_name} {MONTHS_RU[date.month]}"

def get_create_event_keyboard(data: dict) -> InlineKeyboardBuilder:
    """Генерирует клавиатуру для меню создания события."""
    keyboard = InlineKeyboardBuilder()
    today = datetime.now()
    # Первый ряд: Предмет, Название
    subject_text = data.get("subject", "Предмет")
    title_text = data.get("title", "Название")
    if data.get("description"):  # Добавляем "[описание]", если описание заполнено
        title_text += " [описание]"
    keyboard.button(text=subject_text, callback_data="edit_subject")
    keyboard.button(text=title_text, callback_data="edit_title")
    # Второй ряд: Описание, Дата
    description_text = "Описание" if not data.get("description") else "Описание (заполнено)"
    date_str = data.get("date")
    if date_str and data.get("date_changed", False):  # Если дата изменена пользователем
        date = datetime.strptime(date_str, "%Y-%m-%d")
        date_text = format_date_ru(date, today)
    else:
        date_text = "Дата: Завтра"
    keyboard.button(text=description_text, callback_data="edit_description")
    keyboard.button(text=date_text, callback_data="edit_date")
    # Третий ряд: Важность, Темы и очереди
    importance_text = f"Важное: {'Да' if data.get('is_important') else 'Нет'}"
    queue_slots = data.get("queue_slots")
    topic_list_data = data.get("topic_list_data", {"topics": []})
    topics_count = len(topic_list_data["topics"])
    topics_button_text = f"{topics_count} Тем" if topics_count > 0 else "Темы и очереди"
    keyboard.button(text=importance_text, callback_data="edit_importance")
    keyboard.button(text=topics_button_text, callback_data="edit_topics_and_queues")
    # Четвертый ряд: Отмена, Готово
    keyboard.button(text="Отмена", callback_data="cancel_event_creation")
    keyboard.button(text="Готово", callback_data="finish_event_creation")
    keyboard.adjust(2, 2, 2, 2)
    return keyboard

def get_back_keyboard() -> InlineKeyboardBuilder:
    """Генерирует клавиатуру с кнопкой 'Назад'."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="back_to_menu")
    return keyboard

def get_importance_keyboard() -> InlineKeyboardBuilder:
    """Генерирует клавиатуру для выбора важности события."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Да", callback_data="set_importance_true")
    keyboard.button(text="Нет", callback_data="set_importance_false")
    keyboard.button(text="Отмена", callback_data="back_to_menu")
    keyboard.adjust(2, 1)
    return keyboard

def get_date_selection_keyboard(current_date: str = None) -> InlineKeyboardBuilder:
    """Генерирует клавиатуру для выбора даты."""
    keyboard = InlineKeyboardBuilder()
    today = datetime.now()
    if current_date:
        selected_date = datetime.strptime(current_date, "%Y-%m-%d")
    else:
        selected_date = today + timedelta(days=1)  # По умолчанию завтра

    # Первый ряд: Сегодня, Завтра
    keyboard.button(text="Сегодня", callback_data=f"set_date_{today.strftime('%Y-%m-%d')}")
    tomorrow = today + timedelta(days=1)
    keyboard.button(text=format_date_with_day_ru(tomorrow), callback_data=f"set_date_{tomorrow.strftime('%Y-%m-%d')}")

    # Второй ряд: Через 2 дня, Через 3 дня
    day2 = today + timedelta(days=2)
    day3 = today + timedelta(days=3)
    keyboard.button(text=format_date_with_day_ru(day2), callback_data=f"set_date_{day2.strftime('%Y-%m-%d')}")
    keyboard.button(text=format_date_with_day_ru(day3), callback_data=f"set_date_{day3.strftime('%Y-%m-%d')}")

    # Третий ряд: Через 4 дня, Через 5 дней
    day4 = today + timedelta(days=4)
    day5 = today + timedelta(days=5)
    keyboard.button(text=format_date_with_day_ru(day4), callback_data=f"set_date_{day4.strftime('%Y-%m-%d')}")
    keyboard.button(text=format_date_with_day_ru(day5), callback_data=f"set_date_{day5.strftime('%Y-%m-%d')}")

    # Четвертый ряд: Отмена, Через 6 дней
    day6 = today + timedelta(days=6)
    keyboard.button(text="Отмена", callback_data="back_to_menu")
    keyboard.button(text=format_date_with_day_ru(day6), callback_data=f"set_date_{day6.strftime('%Y-%m-%d')}")
    keyboard.adjust(2, 2, 2, 2)
    return keyboard

def get_topics_and_queues_keyboard(topics_count: int) -> InlineKeyboardBuilder:
    """Генерирует клавиатуру для меню 'Темы и очереди'."""
    keyboard = InlineKeyboardBuilder()
    add_topics_text = "Редактировать темы" if topics_count > 0 else "Добавить темы"
    keyboard.button(text=add_topics_text, callback_data="add_topics")
    keyboard.button(text="Добавить очередь", callback_data="add_queue")
    keyboard.button(text="Назад", callback_data="back_to_menu")
    keyboard.adjust(2, 1)
    return keyboard

@router.message(F.text == "➕ Создать событие")
async def start_create_event(message: Message, state: FSMContext, user_repo: UserRepo):
    """Запускает процесс создания события."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        logger.info(f"User check for event creation: {user}, membership: {user.group_membership if user else None}")
        if not user or not user.group_membership or not (user.group_membership.is_leader or user.group_membership.is_assistant):
            await message.answer("У вас нет прав для создания событий.")
            return

        tomorrow = datetime.now() + timedelta(days=1)
        await state.set_state(CreateEvent.main_menu)
        await state.update_data(
            is_important=False,
            date=tomorrow.strftime("%Y-%m-%d"),
            date_changed=False,
            topic_list_data={"topics": []}  # Инициализируем пустой список тем
        )
        keyboard = get_create_event_keyboard({
            "date": tomorrow.strftime("%Y-%m-%d"),
            "date_changed": False,
            "topic_list_data": {"topics": []}
        })
        await message.answer("Создание события", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в start_create_event: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "cancel_event_creation")
async def cancel_event_creation(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo):
    """Отменяет создание события."""
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.answer("Вы не состоите в группе.")
            await state.clear()
            return

        reply_markup = get_main_menu_leader() if user.group_membership.is_leader else get_assistant_menu()
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Создание события отменено.", reply_markup=reply_markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в cancel_event_creation: {e}", exc_info=True)
        await state.clear()
        await callback.message.answer("Произошла ошибка при отмене. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "edit_subject")
async def edit_subject(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на редактирование предмета."""
    try:
        data = await state.get_data()
        subject = data.get("subject", "Пусто")
        await state.set_state(CreateEvent.waiting_for_subject)
        msg = await callback.message.edit_text(f"Предмет: {subject}", reply_markup=get_back_keyboard().as_markup())
        await state.update_data(last_message_id=msg.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_subject: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_subject)
async def process_subject(message: Message, state: FSMContext):
    """Сохраняет введенный предмет и обновляет меню."""
    try:
        subject = message.text.strip()
        if len(subject) < 1 or len(subject) > 255:
            await message.answer("Предмет должен быть от 1 до 255 символов.")
            return

        data = await state.get_data()
        data["subject"] = subject
        last_message_id = data.get("last_message_id")
        if last_message_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        await state.update_data(data)
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await message.delete()
        await message.answer("Создание события", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_subject: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "edit_title")
async def edit_title(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на редактирование названия."""
    try:
        data = await state.get_data()
        title = data.get("title", "Пусто")
        await state.set_state(CreateEvent.waiting_for_title)
        msg = await callback.message.edit_text(f"Название: {title}", reply_markup=get_back_keyboard().as_markup())
        await state.update_data(last_message_id=msg.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_title: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    """Сохраняет введенное название и обновляет меню."""
    try:
        title = message.text.strip()
        if len(title) < 3 or len(title) > 255:
            await message.answer("Название должно быть от 3 до 255 символов.")
            return

        data = await state.get_data()
        data["title"] = title
        last_message_id = data.get("last_message_id")
        if last_message_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        await state.update_data(data)
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await message.delete()
        await message.answer("Создание события", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_title: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "edit_description")
async def edit_description(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на редактирование описания."""
    try:
        data = await state.get_data()
        description = data.get("description", "Пусто")
        await state.set_state(CreateEvent.waiting_for_description)
        msg = await callback.message.edit_text(f"Описание: {description}", reply_markup=get_back_keyboard().as_markup())
        await state.update_data(last_message_id=msg.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_description: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    """Сохраняет введенное описание и обновляет меню."""
    try:
        description = message.text.strip()
        if len(description) > 1000:
            await message.answer("Описание не должно превышать 1000 символов.")
            return

        data = await state.get_data()
        data["description"] = description
        last_message_id = data.get("last_message_id")
        if last_message_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        await state.update_data(data)
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await message.delete()
        await message.answer("Создание события", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_description: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возвращает к главному меню создания события."""
    try:
        data = await state.get_data()
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await callback.message.edit_text("Создание события", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в back_to_menu: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "edit_date")
async def edit_date(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на редактирование даты."""
    try:
        data = await state.get_data()
        date_str = data.get("date")
        if date_str:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            date_text = format_date_ru(date, datetime.now())
        else:
            tomorrow = datetime.now() + timedelta(days=1)
            date_text = format_date_with_day_ru(tomorrow)
        await state.set_state(CreateEvent.waiting_for_date)
        msg = await callback.message.edit_text(
            f"Дата: {date_text}\nВведите дату в формате YYYY-MM-DD или выберите ниже:",
            reply_markup=get_date_selection_keyboard(date_str).as_markup()
        )
        await state.update_data(last_message_id=msg.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_date: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """Сохраняет введенную дату и обновляет меню."""
    try:
        date_str = message.text.strip()
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            await message.answer("Неверный формат даты. Используйте YYYY-MM-DD, например, 2025-06-14.")
            return

        data = await state.get_data()
        data["date"] = date.strftime("%Y-%m-%d")
        data["date_changed"] = True  # Указываем, что дата изменена
        last_message_id = data.get("last_message_id")
        if last_message_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        await state.update_data(data)
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await message.delete()
        await message.answer("Создание события", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_date: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("set_date_"))
async def process_date_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор даты из предложенных."""
    try:
        date_str = callback.data.replace("set_date_", "")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            await callback.message.answer("Неверный формат выбранной даты.")
            return

        data = await state.get_data()
        data["date"] = date_str
        data["date_changed"] = True  # Указываем, что дата изменена
        await state.update_data(data)
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await callback.message.edit_text("Создание события", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в process_date_selection: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "edit_importance")
async def edit_importance(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на редактирование важности."""
    try:
        await state.set_state(CreateEvent.waiting_for_importance)
        msg = await callback.message.edit_text(
            "Важно ли это событие?",
            reply_markup=get_importance_keyboard().as_markup()
        )
        await state.update_data(last_message_id=msg.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_importance: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data.in_(["set_importance_true", "set_importance_false"]))
async def process_importance(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор важности события."""
    try:
        is_important = callback.data == "set_importance_true"
        data = await state.get_data()
        data["is_important"] = is_important
        await state.update_data(data)
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await callback.message.edit_text("Создание события", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в process_importance: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "edit_topics_and_queues")
async def edit_topics_and_queues(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на редактирование тем и очередей."""
    try:
        data = await state.get_data()
        topic_list_data = data.get("topic_list_data", {"topics": []})
        topics_count = len(topic_list_data["topics"])
        await state.set_state(CreateEvent.waiting_for_topics_and_queues)
        keyboard = get_topics_and_queues_keyboard(topics_count)
        warning_text = "\nНажатие на кнопку 'Добавить очередь' сотрёт все темы." if topics_count > 0 else ""
        await callback.message.edit_text(
            f"{topics_count} Тем{warning_text}" if topics_count > 0 else "Темы и очереди",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_topics_and_queues: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "add_queue")
async def add_queue(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на создание очереди."""
    try:
        await state.update_data(topic_list_data={"topics": []})  # Сбрасываем темы
        await state.set_state(CreateEvent.waiting_for_queue_slots)
        msg = await callback.message.edit_text(
            "Введите количество мест в очереди (число):",
            reply_markup=get_back_keyboard().as_markup()
        )
        await state.update_data(last_message_id=msg.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в add_queue: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.message(CreateEvent.waiting_for_queue_slots)
async def process_queue_slots(message: Message, state: FSMContext):
    """Сохраняет количество мест в очереди и обновляет меню."""
    try:
        slots = message.text.strip()
        try:
            max_slots = int(slots)
            if max_slots < 1:
                await message.answer("Количество мест должно быть больше 0.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите корректное число.")
            return

        data = await state.get_data()
        data["queue_slots"] = max_slots
        last_message_id = data.get("last_message_id")
        if last_message_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        await state.update_data(data)
        await state.set_state(CreateEvent.main_menu)
        keyboard = get_create_event_keyboard(data)
        await message.delete()
        await message.answer("Создание события", reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в process_queue_slots: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "finish_event_creation")
async def finish_event_creation(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Завершает создание события."""
    try:
        data = await state.get_data()
        title = data.get("title")
        date_str = data.get("date")

        # Проверка обязательных полей
        if not title or not date_str:
            tomorrow = datetime.now() + timedelta(days=1)
            await state.update_data(
                date=tomorrow.strftime("%Y-%m-%d"),
                date_changed=False
            )
            await callback.message.edit_text(
                "Не заполнены обязательные поля: Название и Дата.",
                reply_markup=get_create_event_keyboard(data).as_markup()
            )
            await state.set_state(CreateEvent.main_menu)
            await callback.answer()
            return

        # Проверка формата даты
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            tomorrow = datetime.now() + timedelta(days=1)
            await state.update_data(
                date=tomorrow.strftime("%Y-%m-%d"),
                date_changed=False
            )
            await callback.message.edit_text(
                "Неверный формат даты. Пожалуйста, исправьте дату.",
                reply_markup=get_create_event_keyboard(data).as_markup()
            )
            await state.set_state(CreateEvent.main_menu)
            await callback.answer()
            return

        # Получение информации о пользователе и группе
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership:
            await callback.message.edit_text("Вы не состоите в группе.")
            await state.clear()
            await callback.answer()
            return

        group_id = str(user.group_membership.group.id)
        created_by_user_id = callback.from_user.id

        # Сбор необязательных полей
        subject = data.get("subject")
        description = data.get("description")
        is_important = data.get("is_important", False)
        queue_slots = data.get("queue_slots")
        topic_list_data = data.get("topic_list_data", {"topics": []})

        # Создание события
        event = await group_repo.create_event(
            group_id=group_id,
            created_by_user_id=created_by_user_id,
            title=title,
            description=description,
            subject=subject,
            date=date_str,
            is_important=is_important
        )

        # Создание очереди, если указаны слоты
        if queue_slots:
            await user_repo.create_queue(event_id=str(event.id), max_slots=queue_slots)

        # Создание списка тем, если есть темы
        if topic_list_data["topics"]:
            topic_list_id = str(uuid4())
            topics = [
                Topic(id=str(uuid4()), topic_list_id=topic_list_id, title=topic["title"], description=topic["description"])
                for topic in topic_list_data["topics"]
            ]
            topic_list = TopicList(
                id=topic_list_id,
                event_id=str(event.id),
                title="Список тем",  # Можно запросить у пользователя
                max_participants_per_topic=10,  # Значение по умолчанию
                created_by_user_id=created_by_user_id,
                topics=topics
            )
            await group_repo.create_topic_list(topic_list)

        if event:
            # Успешное создание
            reply_markup = get_main_menu_leader() if user.group_membership.is_leader else get_assistant_menu()
            await state.clear()
            await callback.message.delete()
            success_message = f"Событие «{title}» успешно создано!"
            if queue_slots:
                success_message += f" Очередь на {queue_slots} мест создана."
            if topic_list_data["topics"]:
                success_message += f" Создан список из {len(topic_list_data['topics'])} тем."
            await callback.message.answer(success_message, reply_markup=reply_markup)
            logger.info(f"Событие создано: {title}, user_id: {created_by_user_id}, group_id: {group_id}")
        else:
            tomorrow = datetime.now() + timedelta(days=1)
            await state.update_data(
                date=tomorrow.strftime("%Y-%m-%d"),
                date_changed=False
            )
            await callback.message.edit_text(
                "Не удалось создать событие. Попробуйте позже.",
                reply_markup=get_create_event_keyboard(data).as_markup()
            )
            await state.set_state(CreateEvent.main_menu)
            logger.error(f"Не удалось создать событие: {title}, user_id: {created_by_user_id}, group_id: {group_id}")

        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в finish_event_creation: {e}", exc_info=True)
        tomorrow = datetime.now() + timedelta(days=1)
        await state.update_data(
            date=tomorrow.strftime("%Y-%m-%d"),
            date_changed=False
        )
        await callback.message.edit_text(
            "Произошла ошибка при создании события. Попробуйте позже.",
            reply_markup=get_create_event_keyboard(data).as_markup()
        )
        await state.set_state(CreateEvent.main_menu)
        await callback.answer()

async def show_topics_and_queues_menu(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        topic_list_data = data.get("topic_list_data", {"topics": []})
        topics_count = len(topic_list_data["topics"])
        keyboard = get_topics_and_queues_keyboard(topics_count)
        warning_text = "\nНажатие на кнопку 'Добавить очередь' сотрёт все темы." if topics_count > 0 else ""
        text = f"{topics_count} Тем{warning_text}" if topics_count > 0 else "Темы и очереди"
        # Проверяем, существует ли сообщение для редактирования
        try:
            await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
        except Exception as e:
            logger.warning(f"Не удалось отредактировать сообщение: {e}. Отправляем новое сообщение.")
            await callback.message.answer(text, reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_topics_and_queues_menu: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()