from sqlalchemy import Column, String, DateTime, Index, ForeignKey, Boolean, Date, BigInteger, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, DeclarativeBase

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
    topic_selections = relationship("TopicSelection", back_populates="user")
    queue_participants = relationship("QueueParticipant", back_populates="user")

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
    """Модель события."""
    __tablename__ = 'events'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    created_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    subject = Column(String(100), nullable=True)
    date = Column(Date, nullable=False)
    is_important = Column(Boolean, default=False)

    group = relationship("Group", back_populates="events")
    topic_lists = relationship("TopicList", back_populates="event", uselist=False, cascade="all, delete-orphan")
    queues = relationship("Queue", back_populates="event", uselist=False, cascade="all, delete-orphan")

class Invite(Base):
    """Модель приглашения в группу."""
    __tablename__ = 'groupinvitations'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    invited_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    invite_token = Column(String(36), unique=True, nullable=False)
    expires_at = Column(Date, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    group = relationship("Group", back_populates="invitations")
    user = relationship("User", foreign_keys=[invited_by_user_id])

class TopicList(Base):
    """Модель списка тем для события."""
    __tablename__ = 'topiclists'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    max_participants_per_topic = Column(Integer, nullable=False)
    created_by_user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="topic_lists")
    topics = relationship("Topic", back_populates="topic_list", cascade="all, delete-orphan")
    created_by = relationship("User")

class Topic(Base):
    """Модель темы в списке тем."""
    __tablename__ = 'topics'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    topic_list_id = Column(UUID(as_uuid=True), ForeignKey('topiclists.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)

    topic_list = relationship("TopicList", back_populates="topics")
    selections = relationship("TopicSelection", back_populates="topic", cascade="all, delete-orphan")

class TopicSelection(Base):
    """Модель выбора темы пользователем."""
    __tablename__ = 'topicselections'

    topic_id = Column(UUID(as_uuid=True), ForeignKey('topics.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)

    topic = relationship("Topic", back_populates="selections")
    user = relationship("User", back_populates="topic_selections")

class Queue(Base):
    """Модель очереди для события."""
    __tablename__ = 'queues'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    max_participants = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="queues")
    participants = relationship("QueueParticipant", back_populates="queue", cascade="all, delete-orphan")

class QueueParticipant(Base):
    """Модель участника очереди."""
    __tablename__ = 'queueparticipants'

    queue_id = Column(UUID(as_uuid=True), ForeignKey('queues.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    position = Column(Integer, nullable=False)

    queue = relationship("Queue", back_populates="participants")
    user = relationship("User", back_populates="queue_participants")