from sqlalchemy import Integer, Float, String, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date as _date
from .base import Base


class ImbalancePrice(Base):
    """
    Imbalance prices per date / interval.

    Attributes
    ----------
    id                  : int   – primary key
    date                : date  – price day  (YYYY-MM-DD)
    interval            : str   – quarter-hour slot (HH:MM)
    positive_imbalance  : float – positive imbalance price
    negative_imbalance  : float – negative imbalance price
    """
    __tablename__ = "imbalance_prices"
    __table_args__ = (
        UniqueConstraint("date", "interval", name="uq_date_interval"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[_date] = mapped_column(Date, nullable=False)
    interval: Mapped[str] = mapped_column(String(5), nullable=False, comment="HH:MM")
    positive_imbalance: Mapped[float] = mapped_column(Float, nullable=True)
    negative_imbalance: Mapped[float] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ImbalancePrice(id={self.id}, date={self.date}, "
            f"interval='{self.interval}', pos={self.positive_imbalance}, "
            f"neg={self.negative_imbalance})>"
        )
