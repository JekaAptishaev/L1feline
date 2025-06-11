import logging
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime, date
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.db.models import User, Group, GroupMember, Invite, Event, TopicList, Topic, TopicSelection

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
        stmt = select(Group).where(Group.id == UUID(group_id))
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

            membership = GroupMember(user_id=user_id, group_id=group.id, is_leader=is_leader)
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

    async def get_group_members(self, group_id: str):
        """Возвращает список участников группы."""
        stmt = select(GroupMember).where(GroupMember.group_id == UUID(group_id))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_group_events(self, group_id: str):
        """Возвращает все события группы с сортировкой по дате."""
        stmt = select(Event).where(Event.group_id == UUID(group_id)).order_by(Event.date)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_event(
        self,
        group_id: str,
        created_by_user_id: int,
        title: str,
        description: str = None,
        subject: str = None,
        date: date = None,
        is_important: bool = False
    ) -> Event:
        """Создаёт новое событие."""
        try:
            group = await self.get_group_by_id(group_id)
            if not group:
                raise ValueError(f"Группа с ID = {group_id} не найдена")

            user_stmt = select(User).where(User.telegram_id == created_by_user_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result:
                raise ValueError(f"Пользователь с telegram_id={created_by_user_id} не найден""")

            event_date = date
            if isinstance(date, str):
                try:
                    event_date = datetime.strptime(date, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError("Неверный формат даты. Используйте YYYY-MM-DD.")

            event = Event(
                group_id=group.id,
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
        stmt = select(Event).where(Event.id == UUID(event_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_invite(self, group_id: str, invited_by_user_id: int, expiry_date: date) -> str:
        try:
            invite_token = str(uuid4())
            invite = Invite(
                group_id=UUID(group_id),
                invited_by_user_id=invited_by_user_id,
                invite_token=invite_token,
                expires_at=expiry_date
            )
            self.session.add(invite)
            await self.session.commit()
            return invite_token
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании приглашения: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании приглашения: {e}")
            await self.session.rollback()
            raise

    async def get_group_by_invite(self, invite_token: str) -> Group | None:
        logger.info(f"Attempting to get group by invite token: {invite_token}")
        stmt = (
            select(Group)
            .join(Invite)
            .where(
                Invite.invite_token == invite_token,
                Invite.expires_at >= datetime.now().date(),
                Invite.is_used == False
            )
        )
        result = await self.session.execute(stmt)
        group = result.scalar_one_or_none()
        if group:
            logger.info(f"Group found: {group.name}, ID: {group.id}")
            invite = (await self.session.execute(select(Invite).where(Invite.invite_token == invite_token))).scalar_one()
            invite.is_used = True
            await self.session.commit()
            logger.info(f"Invite marked as used: {invite.id}")
        else:
            logger.info("No group found or invite is invalid/expired")
        return group

    async def create_topic_list(
        self,
        event_id: str,
        title: str,
        max_participants_per_topic: int,
        created_by_user_id: int,
        topics: List[Tuple[int, str, Optional[str]]]
    ) -> TopicList:
        """Создаёт список тем для события."""
        try:
            event = await self.get_event_by_id(event_id)
            if not event:
                raise ValueError(f"Событие с ID={event_id} не найдено")

            user_stmt = select(User).where(User.telegram_id == created_by_user_id)
            user_result = await self.session.execute(user_stmt)
            if not user_result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={created_by_user_id} не найден")

            topic_list = TopicList(
                event_id=UUID(event_id),
                title=title,
                max_participants_per_topic=max_participants_per_topic,
                created_by_user_id=created_by_user_id
            )
            self.session.add(topic_list)
            await self.session.flush()

            new_topics = [
                Topic(
                    topic_list_id=topic_list.id,
                    title=title,
                    description=description
                )
                for number, title, description in topics
            ]
            self.session.add_all(new_topics)
            await self.session.commit()
            await self.session.refresh(topic_list)
            return topic_list
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании списка тем: {e}", exc_info=True)
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании списка тем: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def reserve_topic(self, topic_id: str, user_id: int) -> Optional[TopicSelection]:
        """Бронирует тему для пользователя."""
        try:
            topic_stmt = select(Topic).where(Topic.id == UUID(topic_id))
            topic_result = await self.session.execute(topic_stmt)
            topic = topic_result.scalar_one_or_none()
            if not topic:
                return None

            stmt = select(func.count()).select_from(TopicSelection).where(
                TopicSelection.topic_id == UUID(topic_id),
                TopicSelection.is_confirmed == True
            )
            result = await self.session.execute(stmt)
            current_count = result.scalar()

            topic_list_stmt = select(TopicList).where(TopicList.id == topic.topic_list_id)
            topic_list_result = await self.session.execute(topic_list_stmt)
            topic_list = topic_list_result.scalar_one_or_none()
            if current_count >= topic_list.max_participants_per_topic:
                return None

            existing_selection = await self.session.execute(
                select(TopicSelection).where(
                    TopicSelection.topic_id == UUID(topic_id),
                    TopicSelection.user_id == user_id
                )
            )
            if existing_selection.scalar_one_or_none():
                return None

            selection = TopicSelection(
                topic_id=UUID(topic_id),
                user_id=user_id
            )
            self.session.add(selection)
            await self.session.commit()
            await self.session.refresh(selection)
            return selection
        except Exception as e:
            logger.error(f"Ошибка при бронировании темы: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def get_topic_list(self, topic_list_id: str) -> Optional[TopicList]:
        """Возвращает список тем с информацией о бронировании."""
        try:
            stmt = (
                select(TopicList)
                .options(
                    selectinload(TopicList.topics).selectinload(Topic.selections).selectinload(TopicSelection.user)
                )
                .where(TopicList.id == UUID(topic_list_id))
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении списка тем: {e}", exc_info=True)
            raise