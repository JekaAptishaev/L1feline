import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_main_menu_unregistered, get_main_menu_leader,  get_regular_member_menu, get_assistant_menu 
from app.handlers.group_leader import CreateGroup, JoinGroup

router = Router()
logger = logging.getLogger(__name__)


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
        
@router.message(F.text == "🔗 Присоединиться по ссылке")
async def start_join_group(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user.group_membership:
            await message.answer("Вы уже состоите в группе. Нельзя присоединиться к другой.")
            return

        await state.set_state(JoinGroup.waiting_for_invite_link)
        await message.answer("Введите пригласительную ссылку для присоединения к группе:")
    except Exception as e:
        logger.error(f"Ошибка в start_join_group: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")