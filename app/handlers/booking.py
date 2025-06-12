# booking.py
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import GroupRepo
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)


class CreateBooking(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_slots_type = State()
    waiting_for_slots_count = State()
    waiting_for_slot_names = State()


@router.message(F.text == "➕ Создать бронь")
async def start_booking_creation(message: Message, state: FSMContext, user_repo: UserRepo):
    """Обработчик начала создания брони"""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("Только староста может создавать брони.")
            return

        await state.set_state(CreateBooking.waiting_for_title)

        # Клавиатура с кнопкой отмены
        cancel_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
        await message.answer(
            "Введите название брони:",
            reply_markup=cancel_kb
        )
    except Exception as e:
        logger.error(f"Ошибка в start_booking_creation: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(CreateBooking.waiting_for_title)
async def process_booking_title(message: Message, state: FSMContext):
    """Обработка названия брони"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание брони отменено.", reply_markup=ReplyKeyboardRemove())
        return

    await state.update_data(title=message.text)
    await state.set_state(CreateBooking.waiting_for_description)

    # Клавиатура с кнопкой пропуска
    skip_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ Пропустить")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Введите описание брони (или пропустите):",
        reply_markup=skip_kb
    )


@router.message(CreateBooking.waiting_for_description)
async def process_booking_description(message: Message, state: FSMContext):
    """Обработка описания брони"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание брони отменено.", reply_markup=ReplyKeyboardRemove())
        return

    description = None
    if message.text != "⏭ Пропустить":
        description = message.text

    await state.update_data(description=description)
    await state.set_state(CreateBooking.waiting_for_slots_type)

    # Клавиатура выбора типа брони
    type_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Бронь темы")],
            [KeyboardButton(text="📍 Бронь места")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Выберите тип брони:",
        reply_markup=type_kb
    )


@router.message(CreateBooking.waiting_for_slots_type)
async def process_slots_type(message: Message, state: FSMContext):
    """Обработка выбора типа брони"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание брони отменено.", reply_markup=ReplyKeyboardRemove())
        return

    if message.text not in ["🎯 Бронь темы", "📍 Бронь места"]:
        await message.answer("Пожалуйста, выберите один из предложенных вариантов.")
        return

    is_theme_booking = message.text == "🎯 Бронь темы"
    await state.update_data(is_theme_booking=is_theme_booking)
    await state.set_state(CreateBooking.waiting_for_slots_count)

    await message.answer(
        "Введите количество слотов для брони:",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(CreateBooking.waiting_for_slots_count)
async def process_slots_count(message: Message, state: FSMContext):
    """Обработка количества слотов"""
    try:
        slots_count = int(message.text)
        if slots_count <= 0 or slots_count > 20:
            await message.answer("Введите число от 1 до 20.")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")
        return

    data = await state.get_data()
    is_theme_booking = data.get('is_theme_booking', False)

    await state.update_data(slots_count=slots_count)

    if is_theme_booking:
        await state.set_state(CreateBooking.waiting_for_slot_names)
        await state.update_data(current_slot=1, slot_names=[])

        # Клавиатура для редактирования
        edit_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✏️ Изменить предыдущую")],
                [KeyboardButton(text="❌ Отмена")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            f"Введите название темы 1 из {slots_count}:",
            reply_markup=edit_kb
        )
    else:
        # Для брони мест сразу создаем
        await create_booking_complete(message, state)


async def create_booking_complete(message: Message, state: FSMContext, group_repo: GroupRepo):
    """Завершение создания брони"""
    data = await state.get_data()
    title = data['title']
    description = data.get('description')
    slots_count = data['slots_count']
    is_theme_booking = data['is_theme_booking']

    # Здесь будет логика сохранения брони в БД
    # Для примера просто выводим результат

    slot_type = "тем" if is_theme_booking else "мест"
    result_message = (
        f"✅ Бронь создана!\n"
        f"Название: {title}\n"
        f"Описание: {description or 'отсутствует'}\n"
        f"Тип: Бронь {slot_type}\n"
        f"Количество: {slots_count}"
    )

    if is_theme_booking:
        slot_names = data.get('slot_names', [])
        result_message += "\nТемы:\n" + "\n".join(
            [f"{i + 1}. {name}" for i, name in enumerate(slot_names)]
        )

    await message.answer(
        result_message,
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()


@router.message(CreateBooking.waiting_for_slot_names)
async def process_slot_name(message: Message, state: FSMContext, group_repo: GroupRepo):
    """Обработка названий тем"""
    data = await state.get_data()
    current_slot = data['current_slot']
    slots_count = data['slots_count']
    slot_names = data['slot_names']

    if message.text == "✏️ Изменить предыдущую":
        if current_slot > 1:
            current_slot -= 1
            slot_names.pop()
            await state.update_data(current_slot=current_slot, slot_names=slot_names)
            await message.answer(
                f"Введите новое название темы {current_slot} из {slots_count}:"
            )
        else:
            await message.answer("Нет предыдущей темы для изменения.")
        return

    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание брони отменено.", reply_markup=ReplyKeyboardRemove())
        return

    # Сохраняем название темы
    slot_names.append(message.text)
    await state.update_data(slot_names=slot_names)

    if current_slot == slots_count:
        # Все темы введены
        await create_booking_complete(message, state, group_repo)
    else:
        # Запрашиваем следующую тему
        next_slot = current_slot + 1
        await state.update_data(current_slot=next_slot)

        edit_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✏️ Изменить предыдущую")],
                [KeyboardButton(text="❌ Отмена")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            f"Введите название темы {next_slot} из {slots_count}:",
            reply_markup=edit_kb
        )