# app/db/models.py
from sqlalchemy import BigInteger, String, Column, DateTime, func, Index, Boolean, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass

class User(Base):
    """Модель пользователя Telegram."""
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True, doc="Уникальный идентификатор пользователя в Telegram")
    telegram_username = Column(String(50), nullable=True, doc="Имя пользователя в Telegram (@username)")
    first_name = Column(String(50), nullable=False, doc="Имя пользователя")
    last_name = Column(String(50), nullable=True, doc="Фамилия пользователя")
    middle_name = Column(String(50), nullable=True, doc="Отчество пользователя (если есть)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), doc="Дата и время создания записи")
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), doc="Дата и время последней активности пользователя")
    notification_settings = Column(JSONB, nullable=True, doc="Настройки уведомлений пользователя в формате JSON")

    group_membership = relationship("GroupMember", back_populates="user", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_user_telegram_username', 'telegram_username'),
    )

    def __repr__(self):
        return (f"<User(id={self.telegram_id}, name='{self.first_name} {self.last_name or ''}', "
                f"telegram_username='{self.telegram_username or ''}')>")

class Group(Base):
    """Модель группы."""
    __tablename__ = 'groups'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    creator_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    """Модель участника группы."""
    __tablename__ = 'groupmembers'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    is_leader = Column(Boolean, default=False, nullable=False)
    is_assistant = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_groupmember_user_id', 'user_id'),
        Index('idx_groupmember_group_id', 'group_id'),
    )

    user = relationship("User", back_populates="group_membership")
    group = relationship("Group", back_populates="members")