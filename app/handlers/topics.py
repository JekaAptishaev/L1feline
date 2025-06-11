import logging
import re
from uuid import UUID
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from app.db.repository import GroupRepo, UserRepo
from app.keyboards.reply import get_main_menu_leader, get_main_menu_member
from sqlalchemy import select
from app.db.models import TopicList, Topic, TopicSelection, Event

router = Router()
logger = logging.getLogger(__name__)

class CreateTopicList(StatesGroup):
    waiting_for_event_id = State()
    waiting_for_title = State()
    waiting_for_max_participants = State()
    waiting_for_topics = State()

class ReserveTopic(StatesGroup):
    waiting_for_topic_list_id = State()
    waiting_for_topic_id = State()

@router.message(F.text == "📋 Создать список тем")
async def start_create_topic_list(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Начинает процесс создания списка тем для старосты."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("У вас нет прав для создания списка тем.")
            return

        group_id = user.group_membership.group.id
        events = await group_repo.get_group_events(str(group_id))
        if not events:
            await message.answer("Нет доступных событий. Создайте событие сначала.")
            return

        event_list = "\n".join([f"{e.id}: {e.title} ({e.date.strftime('%Y-%m-%d')})" for e in events])
        await state.set_state(CreateTopicList.waiting_for_event_id)
        await message.answer(f"Выберите событие, введя его ID:\n{event_list}")
    except Exception as e:
        logger.error(f"Ошибка в start_create_topic_list: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateTopicList.waiting_for_event_id)
async def process_event_id(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Обрабатывает выбор события."""
    try:
        event_id = message.text.strip()
        try:
            UUID(event_id)
        except ValueError:
            await message.answer("Неверный формат ID события. Введите UUID.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            await state.clear()
            return

        group_id = user.group_membership.group.id
        event = await group_repo.get_event_by_id(event_id)
        if not event or event.group_id != group_id:
            await message.answer("Событие не найдено или не принадлежит вашей группе.")
            return

        await state.update_data(event_id=event_id)
        await state.set_state(CreateTopicList.waiting_for_title)
        await message.answer("Введите название списка тем:")
    except Exception as e:
        logger.error(f"Ошибка в process_event_id: {e}", exc_info=True)
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateTopicList.waiting_for_title)
async def process_topic_list_title(message: Message, state: FSMContext):
    """Обрабатывает название списка тем."""
    try:
        title = message.text.strip()
        if not 1 <= len(title) <= 255:
            await message.answer("Название должно быть от 1 до 255 символов.")
            return

        await state.update_data(title=title)
        await state.set_state(CreateTopicList.waiting_for_max_participants)
        await message.answer("Введите максимальное количество участников на одну тему (например, 1):")
    except Exception as e:
        logger.error(f"Ошибка в process_topic_list_title: {e}", exc_info=True)
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateTopicList.waiting_for_max_participants)
async def process_max_participants(message: Message, state: FSMContext):
    """Обрабатывает максимальное количество участников."""
    try:
        max_participants = message.text.strip()
        try:
            max_participants = int(max_participants)
            if max_participants < 1:
                raise ValueError
        except ValueError:
            await message.answer("Введите положительное целое число.")
            return

        await state.update_data(max_participants_per_topic=max_participants)
        await state.set_state(CreateTopicList.waiting_for_topics)
        await message.answer(
            "Введите список тем в формате:\n1. Название темы\n2. Название другой темы\n...\n(каждая тема с новой строки, начиная с номера)"
        )
    except Exception as e:
        logger.error(f"Ошибка в process_max_participants: {e}", exc_info=True)
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(CreateTopicList.waiting_for_topics)
async def process_topics_input(message: Message, state: FSMContext, group_repo: GroupRepo, user_repo: UserRepo):
    """Обрабатывает введённый список тем."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership or not user.group_membership.is_leader:
            await message.answer("У вас нет прав для создания списка тем.")
            await state.clear()
            return

        topics_text = message.text.strip().split("\n")
        topics = []
        for line in topics_text:
            match = re.match(r'^\s*(\d+)\.\s*(.+)$', line)
            if not match:
                await message.answer("Неверный формат. Используйте: '1. Название темы' на каждой строке.")
                return
            number, title = match.groups()
            try:
                number = int(number)
                if number < 1:
                    raise ValueError
                title = title.strip()
                if not 1 <= len(title) <= 255:
                    await message.answer("Название темы должно быть от 1 до 255 символов.")
                    return
                topics.append((number, title, None))
            except ValueError:
                await message.answer("Номер темы должен быть положительным целым числом.")
                return

        data = await state.get_data()
        event_id = data.get("event_id")
        title = data.get("title")
        max_participants_per_topic = data.get("max_participants_per_topic")

        await group_repo.create_topic_list(
            event_id=event_id,
            title=title,
            max_participants_per_topic=max_participants_per_topic,
            created_by_user_id=user.telegram_id,
            topics=topics
        )
        await state.clear()
        await message.answer(
            f"Список тем «{title}» успешно создан! Участники могут бронировать темы.",
            reply_markup=get_main_menu_leader()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_topics_input: {e}", exc_info=True)
        await state.clear()
        await message.answer("Произошла ошибка при создании тем. Попробуйте позже.")

@router.message(F.text == "📋 Бронировать тему")
async def start_reserve_topic(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Начинает процесс бронирования темы."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе. Присоединитесь к группе сначала.")
            return

        group_id = user.group_membership.group.id
        topic_lists_stmt = select(TopicList).join(Event).where(Event.group_id == group_id)
        topic_lists_result = await group_repo.session.execute(topic_lists_stmt)
        topic_lists = topic_lists_result.scalars().all()

        if not topic_lists:
            await message.answer("Нет доступных списков тем для вашей группы.")
            return

        topic_list_info = "\n".join([f"{tl.id}: {tl.title} (Событие: {tl.event.title})" for tl in topic_lists])
        await state.set_state(ReserveTopic.waiting_for_topic_list_id)
        await message.answer(f"Выберите список тем, введя его ID:\n{topic_list_info}")
    except Exception as e:
        logger.error(f"Ошибка в start_reserve_topic: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(ReserveTopic.waiting_for_topic_list_id)
async def process_topic_list_id(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Обрабатывает выбор списка тем для бронирования."""
    try:
        topic_list_id = message.text.strip()
        try:
            topic_list_id = UUID(topic_list_id)
        except ValueError:
            await message.answer("Неверный формат ID списка тем. Введите UUID.")
            return

        topic_list = await group_repo.get_topic_list(str(topic_list_id))
        if not topic_list:
            await message.answer("Список тем не найден.")
            return

        topics = topic_list.topics
        if not topics:
            await message.answer("В этом списке нет тем.")
            return

        topic_info = []
        for topic in topics:
            selections = [s for s in topic.selections if s.is_confirmed]
            available = topic_list.max_participants_per_topic - len(selections)
            status = f"Свободно: {available}" if available > 0 else "Занято"
            topic_info.append(f"{topic.id}: {topic.title} ({status})")

        await state.update_data(topic_list_id=str(topic_list_id))
        await state.set_state(ReserveTopic.waiting_for_topic_id)
        await message.answer(f"Выберите тему, введя её ID:\n" + "\n".join(topic_info))
    except Exception as e:
        logger.error(f"Ошибка в process_topic_list_id: {e}", exc_info=True)
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(ReserveTopic.waiting_for_topic_id)
async def process_topic_id(message: Message, state: FSMContext, user_repo: UserRepo, group_repo: GroupRepo):
    """Обрабатывает выбор темы для бронирования."""
    try:
        topic_id = message.text.strip()
        try:
            topic_id = UUID(topic_id)
        except ValueError:
            await message.answer("Неверный формат ID темы. Введите UUID.")
            return

        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе.")
            await state.clear()
            return

        selection = await group_repo.reserve_topic(str(topic_id), user.telegram_id)
        if not selection:
            await message.answer("Тема не найдена, уже забронирована или превышен лимит участников.")
            await state.clear()
            return

        topic_stmt = select(Topic).where(Topic.id == UUID(topic_id))
        topic_result = await group_repo.session.execute(topic_stmt)
        topic = topic_result.scalar_one_or_none()

        await state.clear()
        await message.answer(
            f"Вы успешно забронировали тему «{topic.title}»! Ожидается подтверждение старостой.",
            reply_markup=get_main_menu_member()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_topic_id: {e}", exc_info=True)
        await state.clear()
        await message.answer("Произошла ошибка при бронировании темы. Попробуйте позже.")

@router.message(F.text == "📋 Просмотреть темы")
async def view_topics(message: Message, user_repo: UserRepo, group_repo: GroupRepo):
    """Показывает список тем и их бронирования."""
    try:
        user = await user_repo.get_user_with_group_info(message.from_user.id)
        if not user or not user.group_membership:
            await message.answer("Вы не состоите в группе. Присоединитесь к группе сначала.")
            return

        group_id = user.group_membership.group.id
        topic_lists_stmt = select(TopicList).join(Event).where(Event.group_id == group_id)
        topic_lists_result = await group_repo.session.execute(topic_lists_stmt)
        topic_lists = topic_lists_result.scalars().all()

        if not topic_lists:
            await message.answer("Нет доступных списков тем для вашей группы.")
            return

        response = []
        for topic_list in topic_lists:
            topic_list = await group_repo.get_topic_list(str(topic_list.id))
            response.append(f"Список тем: {topic_list.title} (Событие: {topic_list.event.title})")
            for topic in topic_list.topics:
                selections = [s for s in topic.selections if s.is_confirmed]
                if selections:
                    participants = ", ".join(
                        [f"{s.user.first_name} {s.user.last_name or ''} (@{s.user.telegram_username or 'без имени'})" for s in selections]
                    )
                    response.append(f"- {topic.title}: {participants}")
                else:
                    response.append(f"- {topic.title}: Свободно")

        await message.answer("\n".join(response))
    except Exception as e:
        logger.error(f"Ошибка в view_topics: {e}", exc_info=True)
        await message.answer("Произошла ошибка при просмотре тем. Попробуйте позже.")