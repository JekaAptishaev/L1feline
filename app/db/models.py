from sqlalchemy import Column, String, DateTime, Index, ForeignKey, Boolean, Date, BigInteger, text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime
import uuid

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
    created_topic_lists = relationship("TopicList", back_populates="creator", foreign_keys="TopicList.created_by_user_id")
    topic_selections = relationship("TopicSelection", back_populates="user", foreign_keys="TopicSelection.user_id")
    confirmed_selections = relationship("TopicSelection", back_populates="confirmer", foreign_keys="TopicSelection.confirmed_by_user_id")

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
    invitations = relationship("Invite", back_populates="group")
    events = relationship("Event", back_populates="group", cascade="all, delete-orphan")

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

class Event(Base):
    __tablename__ = 'events'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    created_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    subject = Column(String(100), nullable=True)
    date = Column(Date, nullable=False)
    is_important = Column(Boolean, default=False)
    
    group = relationship("Group", back_populates="events")
    topic_lists = relationship("TopicList", back_populates="event", cascade="all, delete-orphan")

class Invite(Base):
    __tablename__ = "groupinvitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    invited_by_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    invite_token = Column(String, nullable=False, unique=True)
    expires_at = Column(Date, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    group = relationship("Group", back_populates="invitations")

class TopicList(Base):
    """Модель списка тем, привязанного к событию."""
    __tablename__ = 'topiclists'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False, doc="Название списка тем")
    max_participants_per_topic = Column(Integer, nullable=False, doc="Максимальное количество участников на одну тему")
    created_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), doc="Дата и время создания")

    event = relationship("Event", back_populates="topic_lists")
    creator = relationship("User", back_populates="created_topic_lists", foreign_keys=[created_by_user_id])
    topics = relationship("Topic", back_populates="topic_list", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_topiclist_event_id', 'event_id'),
        Index('idx_topiclist_created_by_user_id', 'created_by_user_id'),
    )

    def __repr__(self):
        return f"<TopicList(id={self.id}, title='{self.title}', event_id={self.event_id})>"

class Topic(Base):
    """Модель темы в списке тем."""
    __tablename__ = 'topics'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    topic_list_id = Column(UUID(as_uuid=True), ForeignKey('topiclists.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False, doc="Название темы")
    description = Column(String(1000), nullable=True, doc="Описание темы")

    topic_list = relationship("TopicList", back_populates="topics")
    selections = relationship("TopicSelection", back_populates="topic", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_topic_topic_list_id', 'topic_list_id'),
    )

    def __repr__(self):
        return f"<Topic(id={self.id}, title='{self.title}', topic_list_id={self.topic_list_id})>"

class TopicSelection(Base):
    """Модель выбора темы участником."""
    __tablename__ = 'topicselections'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    topic_id = Column(UUID(as_uuid=True), ForeignKey('topics.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False)
    selected_at = Column(DateTime(timezone=True), server_default=func.now(), doc="Дата и время выбора темы")
    is_confirmed = Column(Boolean, default=False, nullable=False, doc="Подтверждён ли выбор")
    confirmed_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=True, doc="ID пользователя, подтвердившего выбор")

    topic = relationship("Topic", back_populates="selections")
    user = relationship("User", back_populates="topic_selections", foreign_keys=[user_id])
    confirmer = relationship("User", back_populates="confirmed_selections", foreign_keys=[confirmed_by_user_id])

    __table_args__ = (
        Index('idx_topicselection_topic_id', 'topic_id'),
        Index('idx_topicselection_user_id', 'user_id'),
        Index('idx_topicselection_confirmed_by_id', 'confirmed_by_user_id'),
    )

    def __repr__(self):
        return f"<TopicSelection(id={self.id}, topic_id={self.topic_id}, user_id={self.user_id})>"