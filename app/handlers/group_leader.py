import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_main_menu_leader, get_regular_member_menu
from datetime import datetime, timedelta
import uuid

router = Router()
logger = logging.getLogger(__name__)

class CreateInvite(StatesGroup):
    waiting_for_invite_duration = State()

@router.message(F.text == "👥 Участники группы*")
async def handle_group_members(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("У вас нет прав для просмотра участников группы.")
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await message.answer("В группе пока нет участников.")
            return

        member_list = []
        for member in members:
            member_user = await user_repo.get_user_with_group_info(member.user_id)
            if member_user:
                role = "Староста" if member.is_leader else "Ассистент" if member.is_assistant else "Участник"
                member_info = f"{member_user.first_name} {member_user.last_name or ''} (@{member_user.telegram_username or 'без имени'}) - {role}"
                member_list.append(member_info)

        response = f"Участники группы «{group.name}»:\n" + "\n".join(member_list)
        await message.answer(response)
    except Exception as e:
        logger.error(f"Ошибка в handle_group_members: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка участников. Попробуйте позже.")

@router.message(F.text == "🔗 Создать приглашение")
async def start_create_invite(message: Message, state: FSMContext, user_repo: UserRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("У вас нет прав для создания приглашений.")
            return

        await state.set_state(CreateInvite.waiting_for_invite_duration)
        await message.answer("Введите срок действия приглашения в днях (например, 7):")
    except Exception as e:
        logger.error(f"Ошибка в start_create_invite: {e}")
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateInvite.waiting_for_invite_duration)
async def process_invite_duration(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    try:
        duration = message.text.strip()
        try:
            duration_days = int(duration)
            if duration_days <= 0:
                await message.answer("Срок действия должен быть положительным числом.")
                return
        except ValueError:
            await message.answer("Введите целое число дней.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Ошибка: вы не состоите в группе.")
            return

        group = user.group_membership.group
        expiry_date = datetime.now().date() + timedelta(days=duration_days)
        invite_token = await group_repo.create_invite(group.id, user.telegram_id, expiry_date)

        await state.clear()
        await message.answer(
            f"Приглашение создано!\nКлюч: {invite_token}\nСрок действия: до {expiry_date.strftime('%Y-%m-%d')}"
        )
    except Exception as e:
        logger.error(f"Ошибка в process_invite_duration: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при создании приглашения. Попробуйте позже.")