import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from app.db.repository import GroupRepo
from app.keyboards.reply import get_main_menu_leader

router = Router()
logger = logging.getLogger(__name__)

class CreateGroup(StatesGroup):
    waiting_for_name = State()

@router.message(CreateGroup.waiting_for_name)
async def process_group_name(message: Message, state: FSMContext, group_repo: GroupRepo):
    try:
        group_name = message.text.strip()
        if len(group_name) < 3:
            await message.answer("Название слишком короткое. Пожалуйста, введите название от 3 символов.")
            return
        if len(group_name) > 255:
            await message.answer("Название слишком длинное. Пожалуйста, введите название до 255 символов.")
            return

        await group_repo.create_group(name=group_name, creator_id=message.from_user.id)

        await state.clear()
        await message.answer(
            f"🎉 Группа «{group_name}» успешно создана! Вы теперь её староста.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_group_name: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при создании группы. Попробуйте позже.")

@router.message(F.text == "📅 События и Бронь")
async def handle_events_and_booking(message: Message):
    try:
        await message.answer("Раздел 'События и Бронь' в разработке.")
    except Exception as e:
        logger.error(f"Ошибка в handle_events_and_booking: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "👥 Участники группы")
async def handle_group_members(message: Message):
    try:
        await message.answer("Раздел 'Участники группы' в разработке.")
    except Exception as e:
        logger.error(f"Ошибка в handle_group_members: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "⚙️ Настройки группы")
async def handle_group_settings(message: Message):
    try:
        await message.answer("Раздел 'Настройки группы' в разработке.")
    except Exception as e:
        logger.error(f"Ошибка в handle_group_settings: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")