from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, update, text
from app.db.models import User, Group, GroupMember, Event, Invite, TopicList, Topic
from datetime import datetime, timedelta
import uuid
import logging
import json
from aiogram import Bot  # Импортируем Bot

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
                    middle_name=None,
                    notification_settings={}
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

    async def create_queue(self, event_id: str, max_slots: int) -> bool:
        try:
            event = await self.session.execute(select(Event).where(Event.id == event_id))
            event = event.scalar_one_or_none()
            if not event:
                raise ValueError(f"Событие с event_id={event_id} не найдено")

            stmt = select(GroupMember).where(GroupMember.group_id == event.group_id)
            result = await self.session.execute(stmt)
            members = result.scalars().all()

            for member in members:
                user = await self.get_user_with_group_info(member.user_id)
                if user:
                    notification_settings = user.notification_settings or {}
                    notification_settings[str(event_id)] = {
                        "max_slots": max_slots,
                        "entries": {}
                    }
                    await self.session.execute(
                        update(User)
                        .where(User.telegram_id == user.telegram_id)
                        .values(notification_settings=notification_settings)
                    )
            await self.session.commit()
            logger.info(f"Очередь для события event_id={event_id} создана с max_slots={max_slots}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при создании очереди: {e}")
            await self.session.rollback()
            raise

    async def join_queue(self, event_id: str, user_id: int) -> tuple[bool, str, bool]:
        """Добавляет пользователя в очередь для события, возвращая статус нахождения в очереди."""
        try:
            event = await self.session.execute(select(Event).where(Event.id == event_id))
            event = event.scalar_one_or_none()
            if not event:
                return False, "Событие не найдено", False

            stmt = select(GroupMember).where(GroupMember.group_id == event.group_id, GroupMember.user_id == user_id)
            result = await self.session.execute(stmt)
            member = result.scalar_one_or_none()
            if not member:
                return False, "Вы не состоите в группе этого события", False

            stmt = select(GroupMember).where(GroupMember.group_id == event.group_id)
            result = await self.session.execute(stmt)
            members = result.scalars().all()

            queue_data = None
            for member in members:
                user = await self.get_user_with_group_info(member.user_id)
                if user and user.notification_settings and str(event_id) in user.notification_settings:
                    queue_data = user.notification_settings[str(event_id)]
                    break
            if not queue_data:
                return False, "Очередь для этого события не создана", False

            is_in_queue = False
            for position, queued_user_id in queue_data["entries"].items():
                if int(queued_user_id) == user_id:
                    is_in_queue = True
                    return False, "Вы уже заняли место в очереди", is_in_queue

            current_entries = len(queue_data["entries"])
            max_slots = queue_data["max_slots"]
            if current_entries >= max_slots:
                return False, "Все места в очереди заняты", is_in_queue

            position = current_entries + 1
            queue_data["entries"][str(position)] = user_id

            for member in members:
                user = await self.get_user_with_group_info(member.user_id)
                if user:
                    notification_settings = user.notification_settings or {}
                    notification_settings[str(event_id)] = queue_data
                    await self.session.execute(
                        update(User)
                        .where(User.telegram_id == user.telegram_id)
                        .values(notification_settings=notification_settings)
                    )
            await self.session.commit()
            logger.info(f"Пользователь user_id={user_id} записан в очередь события event_id={event_id} на позицию {position}")
            return True, f"Вы записаны на позицию {position}", is_in_queue
        except Exception as e:
            logger.error(f"Ошибка при записи в очередь: {e}")
            await self.session.rollback()
            return False, "Произошла ошибка при записи в очередь", False

    async def leave_queue(self, event_id: str, user_id: int) -> tuple[bool, str]:
        """Удаляет пользователя из очереди и пересчитывает позиции."""
        try:
            event = await self.session.execute(select(Event).where(Event.id == event_id))
            event = event.scalar_one_or_none()
            if not event:
                return False, "Событие не найдено"

            stmt = select(GroupMember).where(GroupMember.group_id == event.group_id, GroupMember.user_id == user_id)
            result = await self.session.execute(stmt)
            member = result.scalar_one_or_none()
            if not member:
                return False, "Вы не состоите в группе этого события"

            stmt = select(GroupMember).where(GroupMember.group_id == event.group_id)
            result = await self.session.execute(stmt)
            members = result.scalars().all()

            queue_data = None
            for member in members:
                user = await self.get_user_with_group_info(member.user_id)
                if user and user.notification_settings and str(event_id) in user.notification_settings:
                    queue_data = user.notification_settings[str(event_id)]
                    break
            if not queue_data:
                return False, "Очередь для этого события не создана"

            user_position = None
            for position, queued_user_id in queue_data["entries"].items():
                if int(queued_user_id) == user_id:
                    user_position = position
                    break

            if not user_position:
                return False, "Вы не записаны в очередь"

            del queue_data["entries"][user_position]

            new_entries = {}
            for pos, uid in sorted(queue_data["entries"].items(), key=lambda x: int(x[0])):
                new_position = str(int(pos) - 1 if int(pos) > int(user_position) else pos)
                new_entries[new_position] = uid
            queue_data["entries"] = new_entries

            for member in members:
                user = await self.get_user_with_group_info(member.user_id)
                if user:
                    notification_settings = user.notification_settings or {}
                    notification_settings[str(event_id)] = queue_data
                    await self.session.execute(
                        update(User)
                        .where(User.telegram_id == user.telegram_id)
                        .values(notification_settings=notification_settings)
                    )
            await self.session.commit()
            logger.info(f"Пользователь user_id={user_id} удалён из очереди события event_id={event_id}")
            return True, "Вы отказались от места в очереди"
        except Exception as e:
            logger.error(f"Ошибка при удалении из очереди: {e}")
            await self.session.rollback()
            return False, "Произошла ошибка при отказе от места"

    async def get_queue_entries(self, event_id: str) -> dict:
        try:
            event = await self.session.execute(select(Event).where(Event.id == event_id))
            event = event.scalar_one_or_none()
            if not event:
                logger.error(f"Событие с event_id={event_id} не найдено")
                return {}

            stmt = select(GroupMember).where(GroupMember.group_id == event.group_id)
            result = await self.session.execute(stmt)
            members = result.scalars().all()

            queue_data = {"max_slots": 0, "entries": {}}
            found = False

            for member in members:
                user = await self.get_user_with_group_info(member.user_id)
                if user and user.notification_settings and str(event_id) in user.notification_settings:
                    user_queue_data = user.notification_settings[str(event_id)]
                    if user_queue_data.get("max_slots", 0) > queue_data["max_slots"]:
                        queue_data["max_slots"] = user_queue_data["max_slots"]
                    for position, user_id in user_queue_data.get("entries", {}).items():
                        queue_data["entries"][position] = user_id
                    found = True

            if not found:
                logger.info(f"Очередь для события event_id={event_id} не найдена")
                return {}

            logger.info(f"Очередь для события event_id={event_id} успешно собрана: {queue_data}")
            return queue_data
        except Exception as e:
            logger.error(f"Ошибка при получении данных очереди: {e}")
            return {}

class GroupRepo:
    def __init__(self, session: AsyncSession, bot: Bot):  # Добавляем bot в конструктор
        self.session = session
        self.bot = bot  # Сохраняем экземпляр Bot

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
        stmt = select(Group).where(Group.id == group_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(self, group_id: str, user_id: int, is_leader: bool = False):
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
        stmt = select(GroupMember).where(GroupMember.group_id == group_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_group_members_except_user(self, group_id: str, exclude_user_id: int):
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

            # Уведомляем всех участников группы, кроме создателя
            members = await self.get_group_members_except_user(group_id, created_by_user_id)
            notification_text = (
                f"Новое событие в группе «{group.name}»:\n"
                f"Название: {title}\n"
                f"Дата: {event_date.strftime('%d.%m.%Y')}\n"
            )
            if description:
                notification_text += f"Описание: {description}\n"
            if subject:
                notification_text += f"Предмет: {subject}\n"
            if is_important:
                notification_text += "⚠️ [Важное]"

            for member in members:
                try:
                    await self.bot.send_message(
                        chat_id=member.user_id,
                        text=notification_text
                    )
                    logger.info(f"Уведомление отправлено пользователю user_id={member.user_id} о событии event_id={event.id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю user_id={member.user_id}: {e}")

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
        stmt = select(Event).where(Event.id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_topic_list(self, topic_list: TopicList):
        try:
            self.session.add(topic_list)
            for topic in topic_list.topics:
                self.session.add(topic)
            await self.session.commit()
            logger.info(f"Список тем создан: id={topic_list.id}, event_id={topic_list.event_id}")
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании списка тем: {e}")
            await self.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании списка тем: {e}")
            await self.session.rollback()
            raise

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
    
    async def delete_event(self, event_id: str):
        try:
            # Проверяем существование события
            stmt = select(Event).where(Event.id == event_id)
            result = await self.session.execute(stmt)
            event = result.scalar_one_or_none()
            if not event:
                logger.error(f"Событие с event_id={event_id} не найдено")
                raise ValueError(f"Событие с ID={event_id} не найдено")

            # Удаляем событие из таблицы events
            await self.session.execute(
                delete(Event).where(Event.id == event_id)
            )

            # Находим всех участников группы
            stmt = select(GroupMember).where(GroupMember.group_id == event.group_id)
            result = await self.session.execute(stmt)
            members = result.scalars().all()

            # Удаляем данные об очереди из notification_settings
            for member in members:
                stmt = select(User).where(User.telegram_id == member.user_id)
                result = await self.session.execute(stmt)
                user = result.scalar_one_or_none()
                if user and user.notification_settings and str(event_id) in user.notification_settings:
                    notification_settings = user.notification_settings.copy()
                    del notification_settings[str(event_id)]
                    await self.session.execute(
                        update(User)
                        .where(User.telegram_id == user.telegram_id)
                        .values(notification_settings=notification_settings)
                    )

            # Фиксируем изменения
            await self.session.commit()
            logger.info(f"Событие event_id={event_id} успешно удалено вместе с очередью")
        except Exception as e:
            logger.error(f"Ошибка при удалении события {event_id}: {e}", exc_info=True)
            await self.session.rollback()
            raise