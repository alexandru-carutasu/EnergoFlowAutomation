from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .base import Base


class User(Base):
    """
    Generic user model – will be extended later.

    Attributes
    ----------
    id         : int  – primary key
    username   : str  – login name
    email      : str  – contact email
    password   : str  – hashed password
    is_active  : bool – soft-delete / deactivation flag
    created_at : datetime
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', active={self.is_active})>"
