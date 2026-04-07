from sqlalchemy import Integer, String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Plant(Base):
    """
    Represents a power plant (parc) belonging to a Client.

    Attributes
    ----------
    id        : int   – primary key
    name      : str   – plant display name
    client_id : int   – FK → clients.id
    max_pwr   : float – maximum power output in MW
    """
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    max_pwr: Mapped[float] = mapped_column(Float, nullable=False, comment="MW")

    # relationships
    client = relationship("Client", back_populates="plants")
    measurements = relationship("Measurement", back_populates="plant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<Plant(id={self.id}, name='{self.name}', "
            f"client_id={self.client_id}, max_pwr={self.max_pwr} MW)>"
        )
