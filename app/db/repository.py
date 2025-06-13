from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, update, text
from app.db.models import User, Group, GroupMember, Event, Invite
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

async def get_or_create_user(self, telegram_id: int, username: str | None, first_name: str | None, last_name: str | None) -> User:
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
                    first_name=first_name or "Неизвестно",
                    last_name=last_name,
                    middle_name=None
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

    async def update_user(self, telegram_id: int, first_name: str, last_name: str, middle_name: str | None, username: str) -> User:
        """Обновляет данные пользователя."""
        try:
            stmt = (
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    telegram_username=username
                )
                .returning(User)
            )
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"Пользователь с telegram_id={telegram_id} не найден")
            await self.session.commit()
            logger.info(f"Пользователь {telegram_id} обновлён: {first_name} {last_name} {middle_name or ''}")
            return user
        except Exception as e:
            logger.error(f"Ошибка при обновлении пользователя: {e}")
            await self.session.rollback()
            raise

    async def check_full_name_exists(self, last_name: str, first_name: str, middle_name: str | None) -> bool:
        """Проверяет, существует ли пользователь с указанным ФИО."""
        try:
            stmt = select(User).where(
                User.last_name == last_name,
                User.first_name == first_name
            )
            if middle_name:
                stmt = stmt.where(User.middle_name == middle_name)
            else:
                stmt = stmt.where(User.middle_name.is_(None))
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            return user is not None
        except Exception as e:
            logger.error(f"Ошибка при проверке уникальности ФИО: {e}")
            raise

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

    async def ban_user(self, group_id: str, user_id: int):
        """Добавляет пользователя в бан-лист группы."""
        try:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await self.session.execute(stmt)
            if not result.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={user_id} не найден")

            stmt = select(Group).where(Group.id == group_id)
            result = await self.session.execute(stmt)
            if not result.scalar_one_or_none():
                raise ValueError(f"Группа с ID={group_id} не найдена")

            banned_user = {
                "group_id": group_id,
                "user_id": user_id,
                "banned_at": datetime.utcnow()
            }
            await self.session.execute(
                text(
                    "INSERT INTO banned_users (group_id, user_id, banned_at) "
                    "VALUES (:group_id, :user_id, :banned_at) "
                    "ON CONFLICT (group_id, user_id) DO NOTHING"
                ),
                banned_user
            )
            await self.session.commit()
            logger.info(f"Пользователь user_id={user_id} добавлен в бан-лист группы group_id={group_id}")
        except Exception as e:
            logger.error(f"Ошибка при добавлении в бан-лист: {e}")
            await self.session.rollback()
            raise

    async def unban_user(self, group_id: str, user_id: int):
        """Удаляет пользователя из бан-листа группы."""
        try:
            await self.session.execute(
                text(
                    "DELETE FROM banned_users "
                    "WHERE group_id = :group_id AND user_id = :user_id"
                ),
                {"group_id": group_id, "user_id": user_id}
            )
            await self.session.commit()
            logger.info(f"Пользователь user_id={user_id} удалён из бан-листа группы group_id={group_id}")
        except Exception as e:
            logger.error(f"Ошибка при удалении из бан-листа: {e}")
            await self.session.rollback()
            raise

    async def get_banned_users(self, group_id: str):
        """Возвращает список заблокированных пользователей в группе."""
        try:
            stmt = text(
                "SELECT banned_users.user_id, users.first_name, users.last_name, users.middle_name, users.telegram_username, banned_users.banned_at "
                "FROM banned_users "
                "JOIN users ON banned_users.user_id = users.telegram_id "
                "WHERE banned_users.group_id = :group_id"
            )
            result = await self.session.execute(stmt, {"group_id": group_id})
            banned_users = result.fetchall()
            return [
                {
                    "user_id": row.user_id,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "middle_name": row.middle_name,
                    "telegram_username": row.telegram_username,
                    "banned_at": row.banned_at
                }
                for row in banned_users
            ]
        except Exception as e:
            logger.error(f"Ошибка при получении бан-листа: {e}")
            raise

    async def is_user_banned(self, group_id: str, user_id: int) -> bool:
        """Проверяет, находится ли пользователь в бан-листе группы."""
        try:
            stmt = text(
                "SELECT 1 FROM banned_users "
                "WHERE group_id = :group_id AND user_id = :user_id"
            )
            result = await self.session.execute(
                stmt,
                {"group_id": group_id, "user_id": user_id}
            )
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"Ошибка при проверке бан-листа: {e}")
            raise

    async def make_assistant(self, group_id: str, user_id: int):
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
                update(GroupMember)
                .where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
                .values(is_assistant=True)
            )
            await self.session.commit()
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при назначении помощника: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при назначении помощника: {e}")
            await self.session.rollback()
            raise

    async def remove_assistant(self, group_id: str, user_id: int):
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
                update(GroupMember)
                .where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
                .values(is_assistant=False)
            )
            await self.session.commit()
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при снятии роли помощника: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при снятии роли помощника: {e}")
            await self.session.rollback()
            raise

    async def get_group_members(self, group_id: str):
        """Возвращает список участников группы."""
        stmt = select(GroupMember).where(GroupMember.group_id == group_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_group_members_except_user(self, group_id: str, exclude_user_id: int):
        """Возвращает список участников группы, кроме указанного пользователя."""
        try:
            stmt = (
                select(GroupMember)
                .where(GroupMember.group_id == group_id, GroupMember.user_id != exclude_user_id)
            )
            result = await self.session.execute(stmt)
            members = result.scalars().all()
            logger.debug(f"Получено {len(members)} участников группы {group_id}, исключая user_id={exclude_user_id}")
            return members
        except Exception as e:
            logger.error(f"Ошибка при получении участников группы, исключая пользователя: {e}")
            raise

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
        stmt = select(Event).where(Event.id == event_id)
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
    
    async def leave_group(self, group_id: str, user_id: int) -> bool:
        """Удаляет участника из группы, если он не лидер."""
        try:
            stmt = (
                select(GroupMember)
                .where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id,
                    GroupMember.is_leader == False
                )
            )
            result = await self.session.execute(stmt)
            member = result.scalar_one_or_none()
            if not member:
                logger.info(f"Участник user_id={user_id} не найден в группе group_id={group_id} или является лидером")
                return False

            await self.session.delete(member)
            await self.session.commit()
            logger.info(f"Участник user_id={user_id} успешно покинул группу group_id={group_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при выходе из группы: {e}")
            await self.session.rollback()
            return False

    async def delete_group(self, group_id: str, leader_id: int) -> bool:
        """Удаляет группу, если пользователь является лидером."""
        try:
            stmt = (
                select(GroupMember)
                .where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == leader_id,
                    GroupMember.is_leader == True
                )
            )
            result = await self.session.execute(stmt)
            leader = result.scalar_one_or_none()
            if not leader:
                logger.info(f"Пользователь user_id={leader_id} не является лидером группы group_id={group_id}")
                return False

            stmt = select(Group).where(Group.id == group_id)
            result = await self.session.execute(stmt)
            group = result.scalar_one_or_none()
            if not group:
                logger.info(f"Группа group_id={group_id} не найдена")
                return False

            await self.session.delete(group)
            await self.session.commit()
            logger.info(f"Группа group_id={group_id} успешно удалена лидером user_id={leader_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении группы: {e}")
            await self.session.rollback()
            return False
