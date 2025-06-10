from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.db.models import User, Group, GroupMember, Event, Invite
from datetime import datetime
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

    async def get_group_members(self, group_id: str):
        """Возвращает список участников группы."""
        stmt = select(GroupMember).where(GroupMember.group_id == group_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_group_events(self, group_id: str):
        """Возвращает все события группы с сортировкой по дате."""
        stmt = select(Event).where(Event.group_id == group_id).order_by(Event.date)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_event(
        self,
        group_id: str,
        created_by_user_id: int,
        title: str,
        description: str = None,
        subject: str = None,
        date: datetime.date = None,  # Изменён тип на datetime.date
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
        stmt = select(Event).where(Event.id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_invite(self, group_id: str, invited_by_user_id: int, expiry_date: datetime.date) -> str:
        try:
            invite_token = str(uuid.uuid4())
            invite = Invite(
                group_id=group_id,
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
            logger.info(f"Invite marked as used: {invite_token}")
        else:
            logger.info("No group found or invite is invalid/expired")
        return group