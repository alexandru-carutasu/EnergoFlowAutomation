"""
DbManager  –  OOP database service for EnergoFlow.

Usage
-----
    from services.dbmanager.DbManager import DbManager
    from config import DATABASE_URL

    db = DbManager(DATABASE_URL)
    db.create_tables()                       # run once / on startup
    client = db.add_client("Enel", "enel@energy.ro", num_plants=3, has_prod=True)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Sequence, Type, TypeVar

from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session, sessionmaker, joinedload

from .models import Base, Client, Plant, Measurement, User, ImbalancePrice

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)


class DbManager:
   
    def __init__(self, database_url: str, echo: bool = False) -> None:
        self.engine = create_engine(database_url, echo=echo, pool_pre_ping=True)
        self._SessionFactory = sessionmaker(bind=self.engine)
        logger.info("DbManager initialised  (%s)", database_url.split("@")[-1])

    def create_tables(self) -> None:
        """Create all tables that don't exist yet."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables ensured.")

    def drop_tables(self) -> None:
        """Drop ALL tables — use with care (dev only)."""
        Base.metadata.drop_all(self.engine)
        logger.warning("All tables dropped.")

    @property
    def session(self) -> Session:
        """Return a new session (caller must close / use context manager)."""
        return self._SessionFactory()

 
    def _add(self, obj: T) -> T:
        with self.session as s:
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj

    def _add_all(self, objs: Sequence[T]) -> Sequence[T]:
        with self.session as s:
            s.add_all(objs)
            s.commit()
            for o in objs:
                s.refresh(o)
            return objs

    def _get_by_id(self, model: Type[T], id_: int) -> T | None:
        with self.session as s:
            return s.get(model, id_)

    def _get_all(self, model: Type[T]) -> list[T]:
        with self.session as s:
            return list(s.scalars(select(model)).all())

    def _update(self, model: Type[T], id_: int, **kwargs: Any) -> T | None:
        with self.session as s:
            obj = s.get(model, id_)
            if obj is None:
                return None
            for k, v in kwargs.items():
                setattr(obj, k, v)
            s.commit()
            s.refresh(obj)
            return obj

    def _delete(self, model: Type[T], id_: int) -> bool:
        with self.session as s:
            obj = s.get(model, id_)
            if obj is None:
                return False
            s.delete(obj)
            s.commit()
            return True

  
    def add_client(self, name: str, email: str, num_plants: int = 0, has_prod: bool = False) -> Client:
        return self._add(Client(name=name, email=email, num_plants=num_plants, has_prod=has_prod))

    def get_client(self, client_id: int) -> Client | None:
        return self._get_by_id(Client, client_id)

    def get_client_by_email(self, email: str) -> Client | None:
        with self.session as s:
            return s.scalars(select(Client).where(Client.email == email)).first()

    def get_all_clients(self) -> list[Client]:
        return self._get_all(Client)

    def update_client(self, client_id: int, **kwargs: Any) -> Client | None:
        return self._update(Client, client_id, **kwargs)

    def delete_client(self, client_id: int) -> bool:
        return self._delete(Client, client_id)

   
    def add_plant(self, name: str, client_id: int, max_pwr: float) -> Plant:
        return self._add(Plant(name=name, client_id=client_id, max_pwr=max_pwr))

    def get_plant(self, plant_id: int) -> Plant | None:
        return self._get_by_id(Plant, plant_id)

    def get_plants_by_client(self, client_id: int) -> list[Plant]:
        with self.session as s:
            return list(s.scalars(select(Plant).where(Plant.client_id == client_id)).all())

    def get_all_plants(self) -> list[Plant]:
        return self._get_all(Plant)

    def get_all_plants_with_client(self) -> list[Plant]:
        """Return all plants with their client relationship eagerly loaded."""
        with self.session as s:
            stmt = select(Plant).options(joinedload(Plant.client))
            return list(s.scalars(stmt).unique().all())

    def update_plant(self, plant_id: int, **kwargs: Any) -> Plant | None:
        return self._update(Plant, plant_id, **kwargs)

    def delete_plant(self, plant_id: int) -> bool:
        return self._delete(Plant, plant_id)

    def add_measurement(
        self,
        plant_id: int,
        date_: date,
        interval: str,
        forecast_val: float | None = None,
        prod_val: float | None = None,
    ) -> Measurement:
        return self._add(
            Measurement(
                plant_id=plant_id,
                date=date_,
                interval=interval,
                forecast_val=forecast_val,
                prod_val=prod_val,
            )
        )

    def add_measurements_bulk(self, rows: list[dict]) -> Sequence[Measurement]:
        """
        Bulk insert measurements.

        Parameters
        ----------
        rows : list of dict
            Each dict must have keys: plant_id, date, interval, forecast_val, prod_val
        """
        objs = [Measurement(**r) for r in rows]
        return self._add_all(objs)

    def get_measurement(self, measurement_id: int) -> Measurement | None:
        return self._get_by_id(Measurement, measurement_id)

    def get_measurements_by_plant_and_date(
        self, plant_id: int, date_: date
    ) -> list[Measurement]:
        with self.session as s:
            stmt = select(Measurement).where(
                and_(Measurement.plant_id == plant_id, Measurement.date == date_)
            ).order_by(Measurement.interval)
            return list(s.scalars(stmt).all())

    def get_measurements_by_plant_and_date_eager(
        self, plant_id: int, date_: date
    ) -> list[Measurement]:
        """Same as get_measurements_by_plant_and_date but with plant eagerly loaded."""
        with self.session as s:
            stmt = (
                select(Measurement)
                .options(joinedload(Measurement.plant))
                .where(and_(Measurement.plant_id == plant_id, Measurement.date == date_))
                .order_by(Measurement.interval)
            )
            return list(s.scalars(stmt).unique().all())

    def get_all_measurements(self) -> list[Measurement]:
        return self._get_all(Measurement)

    def update_measurement(self, measurement_id: int, **kwargs: Any) -> Measurement | None:
        return self._update(Measurement, measurement_id, **kwargs)

    def upsert_measurement(
        self,
        plant_id: int,
        date_: date,
        interval: str,
        forecast_val: float | None = None,
        prod_val: float | None = None,
    ) -> Measurement:
        """Insert or update a measurement (matched on plant_id + date + interval)."""
        with self.session as s:
            stmt = select(Measurement).where(
                and_(
                    Measurement.plant_id == plant_id,
                    Measurement.date == date_,
                    Measurement.interval == interval,
                )
            )
            existing = s.scalars(stmt).first()
            if existing:
                if forecast_val is not None:
                    existing.forecast_val = forecast_val
                if prod_val is not None:
                    existing.prod_val = prod_val
                s.commit()
                s.refresh(existing)
                return existing
            else:
                m = Measurement(
                    plant_id=plant_id,
                    date=date_,
                    interval=interval,
                    forecast_val=forecast_val,
                    prod_val=prod_val,
                )
                s.add(m)
                s.commit()
                s.refresh(m)
                return m

    def delete_measurement(self, measurement_id: int) -> bool:
        return self._delete(Measurement, measurement_id)

    # ──────────────────────────────────────────────
    # USER helpers
    # ──────────────────────────────────────────────
    def add_user(self, username: str, email: str, password: str) -> User:
        return self._add(User(username=username, email=email, password=password))

    def get_user(self, user_id: int) -> User | None:
        return self._get_by_id(User, user_id)

    def get_user_by_username(self, username: str) -> User | None:
        with self.session as s:
            return s.scalars(select(User).where(User.username == username)).first()

    def get_all_users(self) -> list[User]:
        return self._get_all(User)

    def update_user(self, user_id: int, **kwargs: Any) -> User | None:
        return self._update(User, user_id, **kwargs)

    def delete_user(self, user_id: int) -> bool:
        return self._delete(User, user_id)

    # ──────────────────────────────────────────────
    # IMBALANCE PRICE helpers
    # ──────────────────────────────────────────────
    def add_imbalance_price(
        self,
        date_: date,
        interval: str,
        positive_imbalance: float | None = None,
        negative_imbalance: float | None = None,
    ) -> ImbalancePrice:
        return self._add(
            ImbalancePrice(
                date=date_,
                interval=interval,
                positive_imbalance=positive_imbalance,
                negative_imbalance=negative_imbalance,
            )
        )

    def add_imbalance_prices_bulk(self, rows: list[dict]) -> Sequence[ImbalancePrice]:
        """Bulk insert imbalance prices."""
        objs = [ImbalancePrice(**r) for r in rows]
        return self._add_all(objs)

    def get_imbalance_price(self, price_id: int) -> ImbalancePrice | None:
        return self._get_by_id(ImbalancePrice, price_id)

    def get_imbalance_prices_by_date(self, date_: date) -> list[ImbalancePrice]:
        with self.session as s:
            stmt = (
                select(ImbalancePrice)
                .where(ImbalancePrice.date == date_)
                .order_by(ImbalancePrice.interval)
            )
            return list(s.scalars(stmt).all())

    def get_all_imbalance_prices(self) -> list[ImbalancePrice]:
        return self._get_all(ImbalancePrice)

    def upsert_imbalance_price(
        self,
        date_: date,
        interval: str,
        positive_imbalance: float | None = None,
        negative_imbalance: float | None = None,
    ) -> ImbalancePrice:
        
        with self.session as s:
            stmt = select(ImbalancePrice).where(
                and_(ImbalancePrice.date == date_, ImbalancePrice.interval == interval)
            )
            existing = s.scalars(stmt).first()
            if existing:
                if positive_imbalance is not None:
                    existing.positive_imbalance = positive_imbalance
                if negative_imbalance is not None:
                    existing.negative_imbalance = negative_imbalance
                s.commit()
                s.refresh(existing)
                return existing
            else:
                ip = ImbalancePrice(
                    date=date_,
                    interval=interval,
                    positive_imbalance=positive_imbalance,
                    negative_imbalance=negative_imbalance,
                )
                s.add(ip)
                s.commit()
                s.refresh(ip)
                return ip

    def delete_imbalance_price(self, price_id: int) -> bool:
        return self._delete(ImbalancePrice, price_id)
