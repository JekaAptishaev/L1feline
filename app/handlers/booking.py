from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_main_menu_leader

router = Router()


class CreateBooking(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_num_topics = State()
    waiting_for_topics = State()


@router.message(F.text == "📅 Создать бронь")
async def start_create_booking(message: Message, state: FSMContext, user_repo: UserRepo):
    user = await user_repo.get_user_with_group_info(message.from_user.id)
    if not user or not user.group_membership or not user.group_membership.is_leader:
        await message.answer("У вас нет прав для создания брони.")
        return

    await state.set_state(CreateBooking.waiting_for_name)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Отмена", callback_data="cancel_booking")
    await message.answer("Введите название брони:", reply_markup=keyboard.as_markup())


@router.message(CreateBooking.waiting_for_name)
async def process_booking_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(CreateBooking.waiting_for_description)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Пропустить", callback_data="skip_description")
    keyboard.button(text="Отмена", callback_data="cancel_booking")
    await message.answer("Введите описание брони:", reply_markup=keyboard.as_markup())


@router.callback_query(F.data == "skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await state.set_state(CreateBooking.waiting_for_num_topics)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Отмена", callback_data="cancel_booking")
    await callback.message.edit_text("Введите количество тем:", reply_markup=keyboard.as_markup())
    await callback.answer()


@router.message(CreateBooking.waiting_for_description)
async def process_booking_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(CreateBooking.waiting_for_num_topics)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Отмена", callback_data="cancel_booking")
    await message.answer("Введите количество тем:", reply_markup=keyboard.as_markup())


@router.message(CreateBooking.waiting_for_num_topics)
async def process_num_topics(message: Message, state: FSMContext):
    try:
        num_topics = int(message.text)
        if num_topics <= 0:
            raise ValueError("Количество тем должно быть положительным числом.")
        await state.update_data(num_topics=num_topics, current_topic=0, topics=[])
        await state.set_state(CreateBooking.waiting_for_topics)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_booking")
        await message.answer(f"Введите тему 1 из {num_topics}:", reply_markup=keyboard.as_markup())
    except ValueError:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_booking")
        await message.answer("Пожалуйста, введите корректное число:", reply_markup=keyboard.as_markup())


@router.message(CreateBooking.waiting_for_topics)
async def process_topic(message: Message, state: FSMContext):
    data = await state.get_data()
    topics = data['topics']
    current_topic = data['current_topic']
    num_topics = data['num_topics']

    topics.append(message.text)
    current_topic += 1
    await state.update_data(topics=topics, current_topic=current_topic)

    if current_topic < num_topics:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_booking")
        await message.answer(f"Введите тему {current_topic + 1} из {num_topics}:", reply_markup=keyboard.as_markup())
    else:
        # Здесь можно добавить логику сохранения брони в базу данных
        await message.answer("Бронь успешно создана!", reply_markup=get_main_menu_leader())
        await state.clear()


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Создание брони отменено.", reply_markup=get_main_menu_leader())
    await callback.answer()