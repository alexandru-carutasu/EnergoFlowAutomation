from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Client(Base):
    """
    Represents an energy client that sends files.

    Attributes
    ----------
    id          : int   – primary key
    name        : str   – client display name
    email       : str   – email from which files arrive
    num_plants  : int   – number of plants (parcuri) the client has
    has_prod    : bool  – True if the client also sends production data
    """
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    num_plants: Mapped[int] = mapped_column(Integer, default=0)
    has_prod: Mapped[bool] = mapped_column(Boolean, default=False)

    # one-to-many → Plant
    plants = relationship("Plant", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<Client(id={self.id}, name='{self.name}', email='{self.email}', "
            f"num_plants={self.num_plants}, has_prod={self.has_prod})>"
        )
