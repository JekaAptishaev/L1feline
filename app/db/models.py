from sqlalchemy import BigInteger, String, Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """Модель пользователя Telegram."""
    
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True, doc="Уникальный идентификатор пользователя в Telegram")
    telegram_username = Column(String, nullable=True, doc="Имя пользователя в Telegram (@username)")
    first_name = Column(String, nullable=False, doc="Имя пользователя")
    last_name = Column(String, nullable=True, doc="Фамилия пользователя")
    middle_name = Column(String, nullable=True, doc="Отчество пользователя (если есть)")
    
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        doc="Дата и время создания записи"
    )
    
    last_active_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        doc="Дата и время последней активности пользователя"
    )
    
    notification_settings = Column(
        JSONB, 
        nullable=True, 
        doc="Настройки уведомлений пользователя в формате JSON"
    )

    def __repr__(self):
        return f"<User(id={self.telegram_id}, name='{self.first_name}')>"
