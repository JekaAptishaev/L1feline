from sqlalchemy import Column, ForeignKey, String, Integer, Boolean, DateTime, Date, func, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, DeclarativeBase
from uuid import uuid4

class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass

class User(Base):
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True, doc="Уникальный идентификатор пользователя в Telegram")
    telegram_username = Column(String(255), nullable=True, doc="Имя пользователя в Telegram (@username)")
    first_name = Column(String(255), nullable=False, doc="Имя пользователя")
    last_name = Column(String(255), nullable=True, doc="Фамилия пользователя")
    middle_name = Column(String(255), nullable=True, doc="Отчество пользователя (если есть)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Дата и время создания записи")
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, doc="Дата и время последней активности")
    notification_settings = Column(JSONB, nullable=True, doc="Настройки уведомлений пользователя")

    group_membership = relationship("GroupMember", back_populates="user", uselist=False, cascade="all, delete-orphan")
    def __repr__(self):
        return f"<User(id={self.telegram_id}, name='{self.first_name} {self.last_name or ''}', telegram_username='{self.telegram_username or ''}')>"

from sqlalchemy import Text

class Group(Base):
    __tablename__ = 'groups'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4(), doc="Уникальный идентификатор группы")
    name = Column(String(255), nullable=False, doc="Название группы")
    description = Column(Text, nullable=True, doc="Описание группы")
    creator_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), doc="ID создателя группы")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Дата создания группы")

    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    invitations = relationship("Invite", back_populates="group", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    __tablename__ = 'groupmembers'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4(), doc="Уникальный идентификатор записи")
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, unique=True, doc="ID пользователя")
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id', ondelete='CASCADE'), nullable=False, doc="ID группы")
    is_leader = Column(Boolean, default=False, nullable=False, doc="Является ли пользователь старостой")
    is_assistant = Column(Boolean, default=False, nullable=False, doc="Является ли пользователь ассистентом")
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Дата присоединения")

    user = relationship("User", back_populates="group_membership")
    group = relationship("Group", back_populates="members")

class Invite(Base):
    __tablename__ = 'groupinvitations'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4(), doc="Уникальный идентификатор приглашения")
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id', ondelete='CASCADE'), nullable=False, doc="ID группы")
    creator_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=False, doc="ID создателя приглашения")
    invite_token = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()), doc="Токен приглашения")
    expires_at = Column(Date, nullable=False, doc="Дата истечения срока действия")
    is_used = Column(Boolean, default=False, nullable=False, doc="Использовано ли приглашение")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Дата создания")

    group = relationship("Group", back_populates="invitations")

class Event(Base):
    __tablename__ = 'events'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4(), doc="Уникальный идентификатор события")
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id', ondelete='CASCADE'), nullable=False, doc="ID группы")
    created_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, doc="ID создателя события")
    title = Column(String(100), nullable=False, doc="Название события")
    description = Column(String(255), nullable=True, doc="Описание события")
    subject = Column(String(100), nullable=True, doc="Тема события")
    date = Column(Date, nullable=False, doc="Дата события")
    is_important = Column(Boolean, default=False, nullable=False, doc="Является ли событие важным")

    group = relationship("Group", back_populates="events")
    topic_lists = relationship("TopicList", back_populates="event", cascade="all, delete-orphan")

class TopicList(Base):
    __tablename__ = 'topiclists'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4(), doc="Уникальный идентификатор списка тем")
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False, doc="ID события")
    title = Column(String(255), nullable=False, doc="Название списка тем")
    max_participants_per_topic = Column(Integer, nullable=False, doc="Максимальное количество участников на тему")
    created_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=False, doc="ID создателя")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Дата создания")

    event = relationship("Event", back_populates="topic_lists")
    topics = relationship("Topic", back_populates="topic_list", cascade="all, delete-orphan")

class Topic(Base):
    __tablename__ = 'topics'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4(), doc="Уникальный идентификатор темы")
    topic_list_id = Column(UUID(as_uuid=True), ForeignKey('topiclists.id', ondelete='CASCADE'), nullable=False, doc="ID списка тем")
    title = Column(String(255), nullable=False, doc="Название темы")
    description = Column(String(1000), nullable=True, doc="Описание темы")

    topic_list = relationship("TopicList", back_populates="topics")
    selections = relationship("TopicSelection", back_populates="topic", cascade="all, delete-orphan")

class TopicSelection(Base):
    __tablename__ = 'topicselections'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4(), doc="Уникальный идентификатор выбора темы")
    topic_id = Column(UUID(as_uuid=True), ForeignKey('topics.id', ondelete='CASCADE'), nullable=False, doc="ID темы")
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, doc="ID пользователя")
    selected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Дата выбора")
    is_confirmed = Column(Boolean, default=False, nullable=False, doc="Подтверждён ли выбор")
    confirmed_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=True, doc="ID подтвердившего пользователя")

    topic = relationship("Topic", back_populates="selections")
    user = relationship("User", foreign_keys=[user_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_user_id])