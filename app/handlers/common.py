import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_main_menu_unregistered, get_main_menu_leader, get_regular_member_menu, get_assistant_menu

router = Router()
logger = logging.getLogger(__name__)

class CreateGroup(StatesGroup):
    waiting_for_name = State()

class JoinGroup(StatesGroup):
    waiting_for_invite_token = State()

class RegisterUser(StatesGroup):
    waiting_for_last_name = State()
    waiting_for_first_name = State()
    waiting_for_middle_name = State()

@router.message(CommandStart())
async def cmd_start(message: Message, user_repo: UserRepo, state: FSMContext):
    """Обработчик команды /start."""
    try:
        user = await user_repo.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username or "",
            first_name= None,
            last_name= None
        )
        await state.clear()

        # Проверяем, заполнены ли ФИО
        if user.group_membership is None and (user.first_name == "Неизвестно" or user.last_name is None):
            await state.set_state(RegisterUser.waiting_for_last_name)
            await message.answer("Пожалуйста, введите вашу фамилию:")
            return

        if user.group_membership:
            group_member = user.group_membership
            if group_member.is_leader:
                await message.answer(
                    f"Добро пожаловать, {user.first_name}! Вы староста группы «{group_member.group.name}».",
                    reply_markup=get_main_menu_leader()
                )
            elif group_member.is_assistant:
                await message.answer(
                    f"Добро пожаловать, {user.first_name}! Вы ассистент группы «{group_member.group.name}».",
                    reply_markup=get_assistant_menu()
                )
            else:
                await message.answer(
                    f"Добро пожаловать, {user.first_name}! Вы участник группы «{group_member.group.name}».",
                    reply_markup=get_regular_member_menu()
                )
        else:
            await message.answer(
                f"Добро пожаловать, {user.first_name}! Вы пока не состоите в группе.",
                reply_markup=get_main_menu_unregistered()
            )
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(RegisterUser.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        last_name = message.text.strip()
        if len(last_name) < 2 or len(last_name) > 50:
            await message.answer("Фамилия должна быть от 2 до 50 символов. Попробуйте снова.")
            return

        await state.update_data(last_name=last_name)
        await state.set_state(RegisterUser.waiting_for_first_name)
        await message.answer("Введите ваше имя:")
    except Exception as e:
        logger.error(f"Ошибка в process_last_name: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(RegisterUser.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        first_name = message.text.strip()
        if len(first_name) < 2 or len(first_name) > 50:
            await message.answer("Имя должно быть от 2 до 50 символов. Попробуйте снова.")
            return

        await state.update_data(first_name=first_name)
        await state.set_state(RegisterUser.waiting_for_middle_name)
        await message.answer("Введите ваше отчество (или отправьте 'Пропустить', если его нет):")
    except Exception as e:
        logger.error(f"Ошибка в process_first_name: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(RegisterUser.waiting_for_middle_name)
async def process_middle_name(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        middle_name = message.text.strip() if message.text.strip().lower() != "пропустить" else None
        if middle_name and (len(middle_name) < 2 or len(middle_name) > 50):
            await message.answer("Отчество должно быть от 2 до 50 символов или 'Пропустить'. Попробуйте снова.")
            return

        data = await state.get_data()
        last_name = data.get("last_name")
        first_name = data.get("first_name")

        # Проверяем уникальность ФИО
        full_name_exists = await user_repo.check_full_name_exists(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name
        )
        if full_name_exists:
            await message.answer(
                f"Пользователь с ФИО {last_name} {first_name} {middle_name or ''} уже существует. "
                "Пожалуйста, введите другую фамилию."
            )
            await state.set_state(RegisterUser.waiting_for_last_name)
            return

        # Обновляем данные пользователя в базе
        await user_repo.update_user(
            telegram_id=message.from_user.id,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            username=message.from_user.username or ""
        )

        await state.clear()
        await message.answer(
            f"Регистрация завершена! Добро пожаловать, {first_name}! Вы пока не состоите в группе.",
            reply_markup=get_main_menu_unregistered()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_middle_name: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "🚀 Создать группу")
async def start_create_group(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user.group_membership:
            await message.answer("Вы уже состоите в группе. Нельзя создать еще одну.")
            return

        logger.info(f"Устанавливаем состояние CreateGroup.waiting_for_name для user_id={message.from_user.id}")
        await state.set_state(CreateGroup.waiting_for_name)
        await message.answer("Отлично! Введите название для вашей новой группы:")
    except Exception as e:
        logger.error(f"Ошибка в start_create_group: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateGroup.waiting_for_name)
async def process_group_name(message: Message, state: FSMContext, group_repo: GroupRepo):
    logger.info(f"Получено сообщение для CreateGroup.waiting_for_name: {message.text}")
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

@router.message(F.text == "🔗 Присоединиться по ключу")
async def start_join_group(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user.group_membership:
            await message.answer("Вы уже состоите в группе. Нельзя присоединиться к другой.")
            return
        await state.set_state(JoinGroup.waiting_for_invite_token)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_join_group")
        await message.answer(
            "Введите ключ доступа для присоединения к группе (например, xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx):",
            reply_markup=keyboard.as_markup()
        )
    except Exception as e:
        logger.error(f"Ошибка в start_join_group: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "cancel_join_group")
async def cancel_join_group(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Присоединение к группе отменено.", reply_markup=get_main_menu_unregistered())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в cancel_join_group: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка при отмене. Попробуйте позже.")

@router.message(JoinGroup.waiting_for_invite_token)
async def process_invite_link(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        access_key = message.text.strip()
        match = re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', access_key)
        if not match:
            await message.answer("Неверный формат ключа доступа. Используйте ключ вида xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.")
            return

        group = await group_repo.get_group_by_invite(access_key)
        if not group:
            await message.answer("Ключ доступа недействителен.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user:
            user = await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name or "Неизвестно",
                last_name=message.from_user.last_name or None
            )

        if await group_repo.is_user_banned(group.id, user.telegram_id):
            await message.answer("Вы не можете зайти, так как вас заблокировали.")
            await state.clear()
            return

        await group_repo.add_member(group_id=group.id, user_id=user.telegram_id, is_leader=False)
        await state.clear()
        await message.answer(
            f"Вы успешно присоединились к группе «{group.name}»!",
            reply_markup=get_regular_member_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_invite_link: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при присоединении. Попробуйте позже.")
