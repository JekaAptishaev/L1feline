from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.models import User, Group, GroupMember
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, telegram_id: int, username: str, first_name: str, last_name: str | None) -> User:
        try:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    telegram_id=telegram_id,
                    telegram_username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)
            return user
        except Exception as e:
            logger.error(f"Ошибка при получении/создании пользователя: {e}")
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
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя с группой: {e}")
            return None

class GroupRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_group(self, name: str, creator_id: int) -> Group:
        """Создает группу и делает создателя старостой."""
        try:
            # Проверяем, существует ли пользователь
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
        except Exception as e:
            logger.error(f"Ошибка при создании группы: {e}")
            raise