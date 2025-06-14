from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from uuid import uuid4
from app.db.models import Topic
import logging

router = Router()
logger = logging.getLogger(__name__)

class TopicListStates(StatesGroup):
    waiting_for_topic_title = State()
    waiting_for_topic_description = State()
    waiting_for_description_text = State()
    waiting_for_delete_topic = State()

def get_topic_list_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить", callback_data="delete_topic")
    builder.button(text="+ Описание", callback_data="add_description")
    builder.button(text="Назад", callback_data="back_to_event")
    builder.button(text="Готово", callback_data="finish_topics")
    builder.adjust(2, 2)
    return builder.as_markup()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="back_to_topics")
    return builder.as_markup()

def format_topics(topics):
    if not topics:
        return "Пусто\n"
    return "\n".join(
        f"{i+1}. {topic['title']}{' [описание]' if topic['description'] else ''}"
        for i, topic in enumerate(topics)
    )

@router.callback_query(F.data == "add_topics")
async def start_add_topics(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Начало добавления тем для user_id={callback.from_user.id}")
    # Не очищаем всё состояние, только инициализируем topic_list_data
    await state.update_data(topic_list_data={"topics": []})
    await callback.message.delete()
    sent_msg = await callback.message.answer(
        text="Темы:\nПусто\nВведите название темы в сообщении",
        reply_markup=get_topic_list_keyboard()
    )
    await state.update_data(last_message_id=sent_msg.message_id)
    await state.set_state(TopicListStates.waiting_for_topic_title)
    logger.info(f"Сообщение отправлено, last_message_id={sent_msg.message_id}")

@router.message(TopicListStates.waiting_for_topic_title, F.text)
async def add_topic_title(message: Message, state: FSMContext):
    topic_title = message.text.strip()
    if len(topic_title) < 1 or len(topic_title) > 255:
        await message.answer("Название темы должно быть от 1 до 255 символов.")
        return
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    if len(topics) >= 50:
        await message.answer("Достигнуто максимальное количество тем (50).")
        return
    topics.append({"id": str(uuid4()), "title": topic_title, "description": None})
    await state.update_data(topic_list_data={"topics": topics})
    await message.delete()
    await message.bot.delete_message(message.chat.id, data["last_message_id"])
    sent_msg = await message.answer(
        text=f"Темы:\n{format_topics(topics)}\nВведите название темы в сообщении",
        reply_markup=get_topic_list_keyboard()
    )
    await state.update_data(last_message_id=sent_msg.message_id)

@router.callback_query(F.data == "add_description", TopicListStates.waiting_for_topic_title)
async def request_description_number(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    if not topics:
        await callback.answer("Нет тем для добавления описания.", show_alert=True)
        return
    await callback.message.edit_text(
        text=f"Напишите номер темы, которой желаете добавить описание:\n{format_topics(topics)}",
        reply_markup=get_back_keyboard()
    )
    await state.update_data(last_message_id=callback.message.message_id)
    await state.set_state(TopicListStates.waiting_for_topic_description)

@router.message(TopicListStates.waiting_for_topic_description, F.text)
async def add_topic_description(message: Message, state: FSMContext):
    try:
        topic_number = int(message.text.strip()) - 1
    except ValueError:
        await message.answer("Пожалуйста, введите корректный номер темы.")
        return
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    if topic_number < 0 or topic_number >= len(topics):
        await message.answer("Номер темы вне диапазона.")
        return
    await state.update_data(selected_topic_number=topic_number)
    await message.delete()
    await message.bot.delete_message(message.chat.id, data["last_message_id"])
    sent_msg = await message.answer(
        text=f"Введите описание для темы {topic_number + 1} '{topics[topic_number]['title']}'",
        reply_markup=get_back_keyboard()
    )
    await state.update_data(last_message_id=sent_msg.message_id)
    await state.set_state(TopicListStates.waiting_for_description_text)

@router.message(TopicListStates.waiting_for_description_text, F.text)
async def save_topic_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if len(description) > 1000:
        await message.answer("Описание не должно превышать 1000 символов.")
        return
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    topic_number = data["selected_topic_number"]
    topics[topic_number]["description"] = description
    await state.update_data(topic_list_data={"topics": topics})
    await message.delete()
    await message.bot.delete_message(message.chat.id, data["last_message_id"])
    sent_msg = await message.answer(
        text=f"Темы:\n{format_topics(topics)}\nВведите название темы в сообщении",
        reply_markup=get_topic_list_keyboard()
    )
    await state.update_data(last_message_id=sent_msg.message_id)
    await state.set_state(TopicListStates.waiting_for_topic_title)

@router.callback_query(F.data == "delete_topic", TopicListStates.waiting_for_topic_title)
async def request_delete_topic_number(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    if not topics:
        await callback.answer("Нет тем для удаления.", show_alert=True)
        return
    await callback.message.edit_text(
        text=f"Введите номер темы, которую желаете удалить:\n{format_topics(topics)}",
        reply_markup=get_back_keyboard()
    )
    await state.update_data(last_message_id=callback.message.message_id)
    await state.set_state(TopicListStates.waiting_for_delete_topic)

@router.message(TopicListStates.waiting_for_delete_topic, F.text)
async def delete_topic(message: Message, state: FSMContext):
    try:
        topic_number = int(message.text.strip()) - 1
    except ValueError:
        await message.answer("Пожалуйста, введите корректный номер темы.")
        return
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    if topic_number < 0 or topic_number >= len(topics):
        await message.answer("Номер темы вне диапазона.")
        return
    topics.pop(topic_number)
    await state.update_data(topic_list_data={"topics": topics})
    await message.delete()
    await message.bot.delete_message(message.chat.id, data["last_message_id"])
    sent_msg = await message.answer(
        text=f"Темы:\n{format_topics(topics)}\nВведите название темы в сообщении",
        reply_markup=get_topic_list_keyboard()
    )
    await state.update_data(last_message_id=sent_msg.message_id)
    await state.set_state(TopicListStates.waiting_for_topic_title)

@router.callback_query(F.data == "back_to_topics", TopicListStates.waiting_for_topic_description)
@router.callback_query(F.data == "back_to_topics", TopicListStates.waiting_for_delete_topic)
@router.callback_query(F.data == "back_to_topics", TopicListStates.waiting_for_description_text)
async def back_to_topics(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    await callback.message.edit_text(
        text=f"Темы:\n{format_topics(topics)}\nВведите название темы в сообщении",
        reply_markup=get_topic_list_keyboard()
    )
    await state.update_data(last_message_id=callback.message.message_id)
    await state.set_state(TopicListStates.waiting_for_topic_title)

@router.callback_query(F.data == "back_to_event", TopicListStates.waiting_for_topic_title)
async def cancel_topic_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Отмена добавления тем для user_id={callback.from_user.id}")
    # Сбрасываем только данные тем, сохраняя остальные поля
    await state.update_data(topic_list_data={"topics": []})
    await callback.message.delete()
    from .group_assistant import show_topics_and_queues_menu
    await show_topics_and_queues_menu(callback, state)

@router.callback_query(F.data == "finish_topics", TopicListStates.waiting_for_topic_title)
async def finish_topic_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Завершение добавления тем для user_id={callback.from_user.id}")
    data = await state.get_data()
    topics = data["topic_list_data"]["topics"]
    if not topics:
        await callback.answer("Добавьте хотя бы одну тему.", show_alert=True)
        return
    await state.update_data(topic_list_data={"topics": topics})
    from .group_assistant import show_topics_and_queues_menu
    await show_topics_and_queues_menu(callback, state)
    logger.info(f"Темы сохранены: {len(topics)} тем")