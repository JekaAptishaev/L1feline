from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete
from app.db.models import User, Group, GroupMember, Event, Invite, TopicList, Topic, TopicSelection, Queue, QueueParticipant
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, telegram_id: int, username: str, first_name: str, last_name: str | None) -> User:
        try:
            logger.info(f"Попытка получить пользователя с telegram_id={telegram_id}")
            stmt = (
                select(User)
                .options(selectinload(User.group_membership).selectinload(GroupMember.group))
                .where(User.telegram_id == telegram_id)
            )
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.info(f"Пользователь не найден, создаём нового: telegram_id={telegram_id}")
                user = User(
                    telegram_id=telegram_id,
                    telegram_username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                self.session.add(user)
                await self.session.commit()
                logger.info("Пользователь добавлен в сессию и коммит выполнен")
                await self.session.refresh(user)
                # Повторно загружаем пользователя с отношением
                stmt = (
                    select(User)
                    .options(selectinload(User.group_membership).selectinload(GroupMember.group))
                    .where(User.telegram_id == telegram_id)
                )
                result = await self.session.execute(stmt)
                user = result.scalar_one_or_none()
                logger.info("Пользователь обновлён с отношением")
            return user
        except Exception as e:
            logger.error(f"Ошибка при получении/создании пользователя: {e}", exc_info=True)
            raise

    async def get_user_with_group_info(self, telegram_id: int) -> User | None:
        """Получает пользователя и информацию о его группе одним запросом."""
        try:
            stmt = (
                select(User)
                .options(selectinload(User.group_membership).selectinload(GroupMember.group))
                .where(User.telegram_id == telegram_id)
            )
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            logger.info(f"User retrieved: {user}, membership: {user.group_membership if user else None}")
            return user
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя с группой: {e}")
            return None

class GroupRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_group(self, name: str, creator_id: int) -> Group:
        """Создает группу и делает создателя старостой."""
        try:
            user_stmt = select(User).where(User.telegram_id == creator_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={creator_id} не найден")

            new_group = Group(name=name, creator_id=creator_id)
            self.session.add(new_group)
            await self.session.flush()

            membership = GroupMember(
                user_id=creator_id,
                group_id=new_group.id,
                is_leader=True
            )
            self.session.add(membership)
            await self.session.commit()
            await self.session.refresh(new_group)
            return new_group
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании группы: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании группы: {e}")
            await self.session.rollback()
            raise

    async def get_group_by_id(self, group_id: str) -> Group | None:
        stmt = select(Group).where(Group.id == group_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(self, group_id: str, user_id: int, is_leader: bool = False):
        """Добавляет пользователя в группу."""
        try:
            group = await self.get_group_by_id(group_id)
            if not group:
                raise ValueError(f"Группа с ID={group_id} не найдена")

            user_stmt = select(User).where(User.telegram_id == user_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={user_id} не найден")

            membership = GroupMember(user_id=user_id, group_id=group_id, is_leader=is_leader)
            self.session.add(membership)
            await self.session.commit()
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при добавлении участника: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при добавлении участника: {e}")
            await self.session.rollback()
            raise

    async def delete_member(self, group_id: str, user_id: int):
        """Удаляет участника из группы."""
        try:
            stmt = (
                select(GroupMember)
                .where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
            )
            result = await self.session.execute(stmt)
            member = result.scalar_one_or_none()
            if not member:
                raise ValueError(f"Участник с user_id={user_id} не найден в группе group_id={group_id}")

            await self.session.execute(
                delete(GroupMember)
                .where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
            )
            await self.session.commit()
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при удалении участника: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при удалении участника: {e}")
            await self.session.rollback()
            raise

    async def get_group_members(self, group_id: str):
        """Возвращает список участников группы."""
        stmt = select(GroupMember).where(GroupMember.group_id == group_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_group_events(self, group_id: str):
        """Возвращает все события группы с сортировкой по дате."""
        stmt = (
            select(Event)
            .where(Event.group_id == group_id)
            .options(
                selectinload(Event.topic_lists),
                selectinload(Event.queues)
            )
            .order_by(Event.date)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_event(
        self,
        group_id: str,
        created_by_user_id: int,
        title: str,
        description: str = None,
        subject: str = None,
        date: datetime.date = None,
        is_important: bool = False
    ) -> Event:
        """Создаёт новое событие с полным набором полей."""
        try:
            group = await self.get_group_by_id(group_id)
            if not group:
                raise ValueError(f"Группа с ID={group_id} не найдена")

            user_stmt = select(User).where(User.telegram_id == created_by_user_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={created_by_user_id} не найден")

            event_date = date
            if isinstance(date, str):
                try:
                    event_date = datetime.strptime(date, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError("Неверный формат даты. Используйте YYYY-MM-DD.")

            event = Event(
                group_id=group_id,
                created_by_user_id=created_by_user_id,
                title=title,
                description=description,
                subject=subject,
                date=event_date,
                is_important=is_important
            )
            self.session.add(event)
            await self.session.commit()
            await self.session.refresh(event)
            return event
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании события: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании события: {e}")
            await self.session.rollback()
            raise

    async def get_event_by_id(self, event_id: str) -> Event | None:
        """Возвращает событие по его ID."""
        stmt = (
            select(Event)
            .where(Event.id == event_id)
            .options(
                selectinload(Event.topic_lists),
                selectinload(Event.queues)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_invite(self, group_id: str, invited_by_user_id: int) -> str:
        try:
            invite_token = str(uuid.uuid4())
            invite = Invite(
                group_id=group_id,
                invited_by_user_id=invited_by_user_id,
                invite_token=invite_token,
                expires_at=datetime(2100, 1, 1).date()
            )
            self.session.add(invite)
            await self.session.commit()
            return invite_token
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании ключа доступа: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании ключа доступа: {e}")
            await self.session.rollback()
            raise

    async def get_group_by_invite(self, invite_token: str) -> Group | None:
        logger.info(f"Попытка получить группу по ключу доступа: {invite_token}")
        stmt = (
            select(Group)
            .join(Invite)
            .where(
                Invite.invite_token == invite_token,
                Invite.expires_at >= datetime.now().date()
            )
        )
        result = await self.session.execute(stmt)
        group = result.scalar_one_or_none()
        if group:
            logger.info(f"Группа найдена: {group.name}, ID: {group.id}")
        else:
            logger.info("Группа не найдена или ключ недействителен")
        return group

    async def create_topic_list(
        self,
        event_id: str,
        title: str,
        max_participants_per_topic: int,
        created_by_user_id: int
    ) -> TopicList:
        """Создает список тем для события."""
        try:
            event = await self.get_event_by_id(event_id)
            if not event:
                raise ValueError(f"Событие с ID={event_id} не найдено")

            user_stmt = select(User).where(User.telegram_id == created_by_user_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={created_by_user_id} не найден")

            topic_list = TopicList(
                event_id=event_id,
                title=title,
                max_participants_per_topic=max_participants_per_topic,
                created_by_user_id=created_by_user_id
            )
            self.session.add(topic_list)
            await self.session.commit()
            await self.session.refresh(topic_list)
            return topic_list
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании списка тем: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании списка тем: {e}")
            await self.session.rollback()
            raise

    async def create_topic(self, topic_list_id: str, title: str) -> Topic:
        """Создает тему в списке тем."""
        try:
            topic_list_stmt = select(TopicList).where(TopicList.id == topic_list_id)
            topic_list_result = await self.session.execute(topic_list_stmt)
            topic_list = topic_list_result.scalar_one_or_none()
            if not topic_list:
                raise ValueError(f"Список тем с ID={topic_list_id} не найден")

            topic = Topic(
                topic_list_id=topic_list_id,
                title=title
            )
            self.session.add(topic)
            await self.session.commit()
            await self.session.refresh(topic)
            return topic
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании темы: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании темы: {e}")
            await self.session.rollback()
            raise

    async def create_queue(
        self,
        event_id: str,
        title: str,
        max_participants: int = None
    ) -> Queue:
        """Создает очередь для события."""
        try:
            event = await self.get_event_by_id(event_id)
            if not event:
                raise ValueError(f"Событие с ID={event_id} не найдено")

            queue = Queue(
                event_id=event_id,
                title=title,
                max_participants=max_participants
            )
            self.session.add(queue)
            await self.session.commit()
            await self.session.refresh(queue)
            return queue
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании очереди: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании очереди: {e}")
            await self.session.rollback()
            raise

    async def get_topic_list_by_event(self, event_id: str) -> TopicList | None:
        """Получает список тем для события."""
        stmt = (
            select(TopicList)
            .where(TopicList.event_id == event_id)
            .options(selectinload(TopicList.topics))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_queue_by_event(self, event_id: str) -> Queue | None:
        """Получает очередь для события."""
        stmt = (
            select(Queue)
            .where(Queue.event_id == event_id)
            .options(selectinload(Queue.participants))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_topics_by_topic_list(self, topic_list_id: str) -> list[Topic]:
        """Получает все темы из списка тем."""
        stmt = (
            select(Topic)
            .where(Topic.topic_list_id == topic_list_id)
            .options(selectinload(Topic.selections))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_topic_selections(self, topic_id: str) -> list[TopicSelection]:
        """Получает выборы пользователей для темы."""
        stmt = select(TopicSelection).where(TopicSelection.topic_id == topic_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_topic_selection(self, topic_id: str, user_id: int) -> TopicSelection:
        """Создает запись о выборе темы пользователем."""
        try:
            topic_stmt = select(Topic).where(Topic.id == topic_id)
            topic_result = await self.session.execute(topic_stmt)
            if not topic_result.scalar_one_or_none():
                raise ValueError(f"Тема с ID={topic_id} не найдена")

            user_stmt = select(User).where(User.telegram_id == user_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={user_id} не найден")

            selection = TopicSelection(
                topic_id=topic_id,
                user_id=user_id
            )
            self.session.add(selection)
            await self.session.commit()
            await self.session.refresh(selection)
            return selection
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании выбора темы: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании выбора темы: {e}")
            await self.session.rollback()
            raise

    async def get_queue_participants(self, queue_id: str) -> list[QueueParticipant]:
        """Получает участников очереди."""
        stmt = (
            select(QueueParticipant)
            .where(QueueParticipant.queue_id == queue_id)
            .order_by(QueueParticipant.position)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_queue_participant(self, queue_id: str, user_id: int, position: int) -> QueueParticipant:
        """Добавляет пользователя в очередь."""
        try:
            queue_stmt = select(Queue).where(Queue.id == queue_id)
            queue_result = await self.session.execute(queue_stmt)
            if not queue_result.scalar_one_or_none():
                raise ValueError(f"Очередь с ID {queue_id} не найдена")

            user_stmt = select(User).where(User.telegram_id == user_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id {user_id} не найден")

            participant = QueueParticipant(
                queue_id=queue_id,
                user_id=user_id,
                position=position
            )
            self.session.add(participant)
            await self.session.commit()
            await self.session.refresh(participant)
            return participant
        except IntegrityError as e:
            logger.error(f"Ошибка при добавлении пользователя в очередь: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя в очередь: {e}")
            await self.session.rollback()
            raise
