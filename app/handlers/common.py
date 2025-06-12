import logging
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.db.repository import UserRepo, GroupRepo
from app.keyboards.reply import get_main_menu_unregistered, get_main_menu_leader, get_regular_member_menu, get_assistant_menu

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
                await message.reply(
                    f"Добро пожаловать, {user.first_name}! Вы староста группы «{group_member.group.name}».",
                    reply_markup=get_main_menu_leader()
                )
            elif group_member.is_assistant:
                await message.reply(
                    f"Добро пожаловать, {user.first_name}! Вы ассистент группы «{group_member.group.name}».",
                    reply_markup=get_assistant_menu()
                )
            else:
                await message.reply(
                    f"Добро пожаловать, {user.first_name}! Вы участник группы «{group_member.group.name}».",
                    reply_markup=get_regular_member_menu()
                )
        else:
            await message.reply(
                f"Добро пожаловать, {user.first_name}! Вы пока не состоите в группе.",
                reply_markup=get_main_menu_unregistered()
            )
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}", exc_info=True)
        await message.reply("Произошла ошибка при инициализации. Попробуйте позже.")

@router.message(F.text == "🚀 Создать группу")
async def start_create_group(message: Message, state: FSMContext, user_repo: UserRepo):
    """Обработчик начала создания группы."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user.group_membership:
            await message.reply("Вы уже состоите в группе. Нельзя создать еще одну.")
            return

        logger.info(f"Устанавливаем состояние CreateGroup.waiting_for_name для user_id={message.from_user.id}")
        await state.set_state(CreateGroup.waiting_for_name)
        await message.reply("Отлично! Введите название для вашей новой группы:")
    except Exception as e:
        logger.error(f"Ошибка в start_create_group: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте позже.")

@router.message(CreateGroup.waiting_for_name)
async def process_group_name(message: Message, state: FSMContext, group_repo: GroupRepo):
    """Обработка названия группы."""
    logger.info(f"Получено сообщение для CreateGroup.waiting_for_name: {message.text}")
    try:
        group_name = message.text.strip()
        if len(group_name) < 3:
            await message.reply("Название слишком короткое. Введите минимум 3 символа.")
            return
        if len(group_name) > 255:
            await message.reply("Название слишком длинное. Максимум 255 символов.")
            return

        await group_repo.create_group(name=group_name, creator_id=message.from_user.id)
        await state.clear()
        await message.reply(
            f"🎉 Группа «{group_name}» успешно создана! Вы теперь её староста.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_group_name: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при создании группы. Попробуйте позже.")

@router.message(F.text == "🔗 Присоединиться по ключу")
async def start_join_group(message: Message, state: FSMContext, user_repo: UserRepo):
    """Обработчик начала присоединения к группе."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if user.group_membership:
            await message.reply("Вы уже состоите в группе. Нельзя присоединиться к другой.")
            return

        logger.info(f"Устанавливаем состояние JoinGroup.waiting_for_invite_token для user_id={message.from_user.id}")
        await state.set_state(JoinGroup.waiting_for_invite_token)
        await message.reply("Введите ключ доступа для группы (например, xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx):")
    except Exception as e:
        logger.error(f"Ошибка в start_join_group: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте позже.")

@router.message(JoinGroup.waiting_for_invite_token)
async def process_invite_link(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработка токена приглашения."""
    try:
        access_key = message.text.strip()
        if not re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', access_key):
            await message.reply("Неверный формат ключа. Используйте формат xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.")
            return

        group = await group_repo.get_group_by_invite(access_key)
        if not group:
            await message.reply("Ключ доступа недействителен или истек.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user:
            user = await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username or "",
                first_name=message.from_user.first_name or "",
                last_name=message.from_user.last_name
            )

        await group_repo.add_member(group_id=group.id, user_id=user.telegram_id, is_leader=False)
        await state.clear()
        await message.reply(
            f"Вы успешно присоединились к группе «{group.name}»!",
            reply_markup=get_regular_member_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_invite_link: {e}", exc_info=True)
        await state.clear()
        await message.reply("Ошибка при присоединении к группе. Попробуйте позже.")

@router.message(F.text == "📋 Мои брони")
async def show_my_bookings(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    """Обработчик команды 'Мои брони'."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.reply("Вы не состоите в группе.")
            return

        group = user.group_membership.group
        events = await group_repo.get_group_events(group.id)
        bookings = []

        for event in events:
            topic_list = await group_repo.get_topic_list_by_event(event.id)
            queue = await group_repo.get_queue_by_event(event.id)

            if topic_list:
                topics = await group_repo.get_topics_by_topic_list(topic_list.id)
                for topic in topics:
                    selections = await group_repo.get_topic_selections(topic.id)
                    if any(selection.user_id == user.telegram_id for selection in selections):
                        bookings.append(
                            f"Событие: {event.title} ({event.date.strftime('%Y-%m-%d')})\n"
                            f"Тема: {topic.title} ({len(selections)}/{topic_list.max_participants_per_topic})"
                        )

            if queue:
                participants = await group_repo.get_queue_participants(queue.id)
                for participant in participants:
                    if participant.user_id == user.telegram_id:
                        bookings.append(
                            f"Событие: {event.title} ({event.date.strftime('%Y-%m-%d')})\n"
                            f"Очередь: место #{participant.position} ({len(participants)}/{queue.max_participants or '∞'})"
                        )

        if not bookings:
            await message.reply("У вас нет активных бронирований.", reply_markup=get_regular_member_menu())
            return

        response = "Ваши брони:\n\n" + "\n\n".join(bookings)
        await message.reply(response, reply_markup=get_regular_member_menu())
    except Exception as e:
        logger.error(f"Ошибка в show_my_bookings: {e}", exc_info=True)
        await message.reply("Ошибка при получении бронирований. Попробуйте позже.")