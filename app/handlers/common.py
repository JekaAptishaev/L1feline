import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_main_menu_unregistered, get_main_menu_leader
from app.handlers.group_leader import CreateGroup, JoinGroup

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        # Получаем пользователя
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        logger.info(f"User from get_user_with_group_info: {user}")
        if not user:
            try:
                user = await user_repo.get_or_create_user(
                    telegram_id=message.from_user.id,
                    username=message.from_user.username or "",
                    first_name=message.from_user.first_name or "",
                    last_name=message.from_user.last_name
                )
                logger.info(f"User created: {user}")
            except Exception as e:
                logger.error(f"Ошибка при создании пользователя: {e}", exc_info=True)
                await message.answer("Не удалось создать пользователя. Попробуйте позже.")
                return

        # Проверка на токен приглашения
        if len(message.text.split()) > 1:
            invite_token = message.text.split()[1]
            group = await group_repo.get_group_by_invite(invite_token)
            if group:
                await group_repo.add_member(group.id, message.from_user.id, is_leader=False)
                await message.answer(f"Вы успешно присоединились к группе «{group.name}»!")
                user = await user_repo.get_user_with_group_info(message.from_user.id)  # Обновляем данные
            else:
                await message.answer("Неверный или истёкший код приглашения.")

        # Определяем ответ в зависимости от членства
        if user.group_membership:
            if user.group_membership.is_leader:
                await message.answer(
                    f"Добро пожаловать, староста группы «{user.group_membership.group.name}»!",
                    reply_markup=get_main_menu_leader()
                )
            else:
                await message.answer(f"Вы участник группы «{user.group_membership.group.name}»")
        else:
            await message.answer(
                "👋 Добро пожаловать! Вы еще не состоите в группе.\n\nСоздайте свою или присоединитесь к существующей.",
                reply_markup=get_main_menu_unregistered()
            )
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        
@router.message(F.text == "🚀 Создать группу")
async def start_create_group(message: Message, state: FSMContext, user_repo: UserRepo):
    logger.info(f"Получено сообщение: {message.text}' для user_id={message.from_user.id}")
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