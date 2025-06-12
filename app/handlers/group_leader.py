import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_main_menu_leader, get_assistant_menu, get_regular_member_menu, get_main_menu_unregistered


router = Router()
logger = logging.getLogger(__name__)

class CreateInvite(StatesGroup):
    waiting_for_invite_duration = State()

class DeleteMember(StatesGroup):
    waiting_for_member_number = State()

class MakeAssistant(StatesGroup):
    waiting_for_member_number = State()

class RemoveAssistant(StatesGroup):
    waiting_for_member_number = State()

@router.message(F.text == "👥 Участники группы*")
async def handle_group_members(message: Message, user_repo: UserRepo, group_repo: GroupRepo, state: FSMContext):
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
        for idx, member in enumerate(members, 1):
            member_user = await user_repo.get_user_with_group_info(member.user_id)
            if member_user:
                role = "Староста" if member.is_leader else "Ассистент" if member.is_assistant else "Участник"
                full_name = f"{member_user.last_name or ''} {member_user.first_name} {member_user.middle_name or ''}".strip()
                member_info = f"{idx}. {full_name} (@{member_user.telegram_username or 'без имени'}) - {role}"
                member_list.append(member_info)

        response = f"Участники группы «{group.name}»:\n" + "\n".join(member_list)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Удалить", callback_data="delete_member")
        keyboard.button(text="Сделать ассистентом", callback_data="make_assistant")
        keyboard.button(text="Убрать ассистента", callback_data="remove_assistant")
        keyboard.adjust(2)
        await message.answer(response, reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.error(f"Ошибка в handle_group_members: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка участников. Попробуйте позже.")

@router.callback_query(F.data == "delete_member")
async def start_delete_member(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await callback.message.answer("У вас нет прав для удаления участников.")
            await callback.answer()
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await callback.message.answer("В группе пока нет участников.")
            await callback.answer()
            return

        await state.update_data(members=members, group_id=group.id)
        await state.set_state(DeleteMember.waiting_for_member_number)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_delete_member")
        await callback.message.answer("Введите номер участника, которого желаете удалить:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_delete_member: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "make_assistant")
async def start_make_assistant(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await callback.message.answer("У вас нет прав для назначения ассистентов.")
            await callback.answer()
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await callback.message.answer("В группе пока нет участников.")
            await callback.answer()
            return

        await state.update_data(members=members, group_id=group.id)
        await state.set_state(MakeAssistant.waiting_for_member_number)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_make_assistant")
        await callback.message.answer("Введите номер участника, которого желаете сделать ассистентом:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_make_assistant: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "remove_assistant")
async def start_remove_assistant(callback: CallbackQuery, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(callback.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await callback.message.answer("У вас нет прав для снятия ассистентов.")
            await callback.answer()
            return

        group = user.group_membership.group
        members = await group_repo.get_group_members(group.id)
        if not members:
            await callback.message.answer("В группе пока нет участников.")
            await callback.answer()
            return

        await state.update_data(members=members, group_id=group.id)
        await state.set_state(RemoveAssistant.waiting_for_member_number)
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_remove_assistant")
        await callback.message.answer("Введите номер участника, с которого желаете снять роль ассистента:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_remove_assistant: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "cancel_delete_member")
async def cancel_delete_member(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Удаление участника отменено.", reply_markup=get_main_menu_leader())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в cancel_delete_member: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка при отмене. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "cancel_make_assistant")
async def cancel_make_assistant(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Назначение ассистента отменено.", reply_markup=get_main_menu_leader())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в cancel_make_assistant: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка при отмене. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "cancel_remove_assistant")
async def cancel_remove_assistant(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Снятие роли ассистента отменено.", reply_markup=get_main_menu_leader())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в cancel_remove_assistant: {e}")
        await state.clear()
        await callback.message.answer("Произошла ошибка при отмене. Попробуйте позже.")
        await callback.answer()

@router.message(DeleteMember.waiting_for_member_number)
async def process_delete_member(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo, bot: Bot):
    try:
        data = await state.get_data()
        members = data.get("members")
        group_id = data.get("group_id")
        if not members or not group_id:
            await message.answer("Ошибка: данные об участниках или группе отсутствуют.")
            await state.clear()
            return

        try:
            member_number = int(message.text.strip())
            if member_number < 1 or member_number > len(members):
                await message.answer("Неверный номер участника. Попробуйте снова.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите корректный номер участника (число).")
            return

        member_to_delete = members[member_number - 1]
        member_user = await user_repo.get_user_with_group_info(member_to_delete.user_id)
        if not member_user:
            await message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return

        if member_user.telegram_id == message.from_user.id:
            await message.answer("Вы не можете удалить самого себя из группы.")
            await state.clear()
            return

        await group_repo.delete_member(group_id=group_id, user_id=member_to_delete.user_id)
        await bot.send_message(
            member_user.telegram_id,
            "Вас выгнали из группы.",
            reply_markup=get_main_menu_unregistered()
        )
        await state.clear()
        await message.answer(
            f"Участник {member_user.first_name} {member_user.last_name or ''} удалён из группы.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_delete_member: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при удалении участника. Попробуйте позже.")

@router.message(MakeAssistant.waiting_for_member_number)
async def process_make_assistant(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo, bot: Bot):
    try:
        data = await state.get_data()
        members = data.get("members")
        group_id = data.get("group_id")
        if not members or not group_id:
            await message.answer("Ошибка: данные об участниках или группе отсутствуют.")
            await state.clear()
            return

        try:
            member_number = int(message.text.strip())
            if member_number < 1 or member_number > len(members):
                await message.answer("Неверный номер участника. Попробуйте снова.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите корректный номер участника (число).")
            return

        member_to_update = members[member_number - 1]
        member_user = await user_repo.get_user_with_group_info(member_to_update.user_id)
        if not member_user:
            await message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return

        if member_to_update.is_leader:
            await message.answer("Этот пользователь уже является старостой.")
            await state.clear()
            return
        if member_to_update.is_assistant:
            await message.answer("Этот пользователь уже является ассистентом.")
            await state.clear()
            return

        await group_repo.make_assistant(group_id=group_id, user_id=member_to_update.user_id)
        await bot.send_message(
            member_user.telegram_id,
            "Поздравляем, вы назначены ассистентом! Используйте новое меню для управления группой.",
            reply_markup=get_assistant_menu()
        )
        await state.clear()
        await message.answer(
            f"Участник {member_user.first_name} {member_user.last_name or ''} назначен ассистентом.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_make_assistant: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при назначении ассистента. Попробуйте позже.")

@router.message(RemoveAssistant.waiting_for_member_number)
async def process_remove_assistant(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo, bot: Bot):
    try:
        data = await state.get_data()
        members = data.get("members")
        group_id = data.get("group_id")
        if not members or not group_id:
            await message.answer("Ошибка: данные об участниках или группе отсутствуют.")
            await state.clear()
            return

        try:
            member_number = int(message.text.strip())
            if member_number < 1 or member_number > len(members):
                await message.answer("Неверный номер участника. Попробуйте снова.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите корректный номер участника (число).")
            return

        member_to_update = members[member_number - 1]
        member_user = await user_repo.get_user_with_group_info(member_to_update.user_id)
        if not member_user:
            await message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return

        if not member_to_update.is_assistant:
            await message.answer("Этот пользователь не является ассистентом.")
            await state.clear()
            return

        await group_repo.remove_assistant(group_id=group_id, user_id=member_to_update.user_id)

        await bot.send_message(
            member_user.telegram_id,
            "Ваша роль ассистента снята. Используйте стандартное меню участника.",
            reply_markup=get_regular_member_menu()
        )
        await state.clear()
        await message.answer(
            f"С участника {member_user.first_name} {member_user.last_name or ''} снята роль ассистента.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_remove_assistant: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при снятии роли ассистента. Попробуйте позже.")

@router.message(F.text == "🔗 Создать приглашение")
async def start_create_invite(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("У вас нет прав для создания ключей доступа.")
            return

        group = user.group_membership.group
        invite_token = await group_repo.create_invite(group.id, user.telegram_id)
        await state.clear()
        await message.answer(
            f"Ключ доступа для группы «{group.name}» успешно создан! Передайте его пользователям для присоединения."
        )
        await message.answer(invite_token)
    except Exception as e:
        logger.error(f"Ошибка в start_create_invite: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при создании ключа доступа. Попробуйте позже.")

@router.message(F.text == "🗑 Удалить группу")
async def delete_group(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("У вас нет прав для удаления группы.")
            return

        group = user.group_membership.group
        success = await group_repo.delete_group(group_id=str(group.id), leader_id=user.telegram_id)
        if success:
            await state.clear()
            await message.answer(
                f"Группа «{group.name}» успешно удалена.",
                reply_markup=get_main_menu_unregistered()
            )
        else:
            await message.answer("Не удалось удалить группу. Убедитесь, что вы лидер группы.")
    except Exception as e:
        logger.error(f"Ошибка в delete_group: {e}")
        await message.answer("Произошла ошибка при удалении группы. Попробуйте позже.")
