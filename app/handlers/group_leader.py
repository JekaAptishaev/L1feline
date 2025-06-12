import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_main_menu_leader

router = Router()
logger = logging.getLogger(__name__)

class CreateInvite(StatesGroup):
    waiting_for_invite_duration = State()

class DeleteMember(StatesGroup):
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
                member_info = f"{idx}. {member_user.first_name} {member_user.last_name or ''} (@{member_user.telegram_username or 'без имени'}) - {role}"
                member_list.append(member_info)

        response = f"Участники группы «{group.name}»:\n" + "\n".join(member_list)
        
        # Добавляем инлайн-кнопку "Удалить" только для старосты
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Удалить", callback_data="delete_member")
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

        # Сохраняем список участников в состоянии для последующего использования
        await state.update_data(members=members, group_id=group.id)
        await state.set_state(DeleteMember.waiting_for_member_number)
        # Отправляем новое сообщение вместо редактирования
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data="cancel_delete_member")
        await callback.message.answer("Введите номер участника, которого желаете удалить:", reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_delete_member: {e}")
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

@router.message(DeleteMember.waiting_for_member_number)
async def process_delete_member(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
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

        # Проверяем, не пытается ли староста удалить самого себя
        if member_user.telegram_id == message.from_user.id:
            await message.answer("Вы не можете удалить самого себя из группы.")
            await state.clear()
            return

        # Удаляем участника
        await group_repo.delete_member(group_id=group_id, user_id=member_to_delete.user_id)
        await state.clear()
        await message.answer(
            f"Участник {member_user.first_name} {member_user.last_name or ''} удалён из группы.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_delete_member: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при удалении участника. Попробуйте позже.")

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
            f"Ключ доступа создан!\nКлюч: {invite_token}\nПередайте этот ключ пользователям для присоединения к группе «{group.name}»."
        )
    except Exception as e:
        logger.error(f"Ошибка в start_create_invite: {e}")
        await state.clear()
        await message.answer("Произошла ошибка при создании ключа доступа. Попробуйте позже.")