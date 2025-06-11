import logging
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_main_menu_unregistered, get_main_menu_leader,  get_regular_member_menu, get_assistant_menu 

router = Router()
logger = logging.getLogger(__name__)

class CreateGroup(StatesGroup):
    waiting_for_name = State()

class JoinGroup(StatesGroup):
    waiting_for_invite_token = State()

@router.message(CommandStart())
async def cmd_start(message: Message, user_repo: UserRepo, state: FSMContext):
    """Обработчик команды /start."""
    try:
        user = await user_repo.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name
        )
        await state.clear()

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
        await message.answer("Введите пригласительную ссылку для присоединения к группе:")
    except Exception as e:
        logger.error(f"Ошибка в start_join_group: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(JoinGroup.waiting_for_invite_token)
async def process_invite_token(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        invite_token = message.text.strip()
        match = re.match(r'^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$', invite_token)
        if not match:
            await message.answer("Неверный формат пригласительногоо токена. Используйте ссылку вида xxxx.")
            return

        invite_token = match.group(1)
        group = await group_repo.get_group_by_invite(invite_token)
        if not group:
            await message.answer("Приглашение недействительно или истекло.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user:
            user = await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )

        await group_repo.add_member(group_id=group.id, user_id=user.telegram_id, is_leader=False)
        await state.clear()
        await message.answer(
            f"Вы успешно присоединились к группе «{group.name}»!",
            reply_markup=get_regular_member_menu())
    except Exception as e:
        logger.error(f"Ошибка в process_invite_token: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при присоединении. Попробуйте позже.")
