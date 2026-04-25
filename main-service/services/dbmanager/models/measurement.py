from sqlalchemy import Integer, Float, String, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date as _date
from .base import Base


class Measurement(Base):
    """
    Forecast and production value for a specific plant / date / interval.

    Attributes
    ----------
    id           : int   – primary key
    plant_id     : int   – FK → plants.id
    date         : date  – measurement day  (YYYY-MM-DD)
    interval     : str   – quarter-hour slot (HH:MM, e.g. "00:00", "00:15")
    forecast_val : float – forecasted value
    prod_val     : float – actual production value (nullable)
    """
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("plant_id", "date", "interval", name="uq_plant_date_interval"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(Integer, ForeignKey("plants.id"), nullable=False)
    date: Mapped[_date] = mapped_column(Date, nullable=False)
    interval: Mapped[str] = mapped_column(String(5), nullable=False, comment="HH:MM")
    forecast_val: Mapped[float] = mapped_column(Float, nullable=True)
    prod_val: Mapped[float] = mapped_column(Float, nullable=True)

    # relationship
    plant = relationship("Plant", back_populates="measurements")

    def __repr__(self) -> str:
        return (
            f"<Measurement(id={self.id}, plant_id={self.plant_id}, "
            f"date={self.date}, interval='{self.interval}', "
            f"forecast={self.forecast_val}, prod={self.prod_val})>"
        )
