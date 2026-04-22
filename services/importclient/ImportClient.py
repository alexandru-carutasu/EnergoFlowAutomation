from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pytz
import requests

from services.dbmanager.DbManager import DbManager

logger = logging.getLogger(__name__)


class ImportClient:
	def __init__(
		self,
		db: DbManager,
		timezone: str = "Europe/Bucharest",
		base_url: str = (
			"https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/"
			"00121002500000000000000000000100/publicReport/estimatedImbalancePrices"
		),
	) -> None:
		self.db = db
		self.local_tz = pytz.timezone(timezone)
		self.base_url = base_url

	def fetch_latest_data(self, days_back: int = 3, days_forward: int = 1) -> list[dict[str, Any]]:
		fetched_data: list[dict[str, Any]] = []

		now_local = datetime.now(tz=self.local_tz)
		start_local = (now_local - timedelta(days=days_back)).replace(
			hour=0,
			minute=0,
			second=0,
			microsecond=0,
		)
		end_local = (now_local + timedelta(days=days_forward)).replace(
			hour=0,
			minute=0,
			second=0,
			microsecond=0,
		)

		str_start_date = start_local.strftime("%Y-%m-%dT%H:%M:%S.000Z")
		str_end_date = end_local.strftime("%Y-%m-%dT%H:%M:%S.000Z")

		url = f"{self.base_url}?timeInterval.from={str_start_date}&timeInterval.to={str_end_date}"

		headers = {
			"Accept": "application/json",
		}

		try:
			response = requests.get(url, headers=headers, timeout=20)
			logger.info("Imbalance status code: %s", response.status_code)

			if not response.text.strip():
				logger.error("Empty response body -> fetch_latest_data")
				return []

			content_type = response.headers.get("Content-Type", "").lower()
			if response.status_code != 200:
				raise Exception(f"Request failed with status code: {response.status_code}, {response.text}")
			if "application/json" not in content_type:
				raise Exception("Response is not in JSON format")

			data = response.json()
			items = data.get("itemList", [])

			seen: set[tuple[Any, Any, Any]] = set()
			for item in items:
				time_from = item.get("timeInterval", {}).get("from")
				if not time_from:
					continue
				try:
					dt_naive = datetime.strptime(time_from, "%Y-%m-%dT%H:%M:%S.000Z")
				except ValueError:
					logger.warning("Skipping item with invalid time: %s", time_from)
					continue

				dt_local = self.local_tz.localize(dt_naive)
				dt_utc = dt_local.astimezone(pytz.utc)

				negative = item.get("estimatedPriceNegativeImbalance")
				positive = item.get("estimatedPricePositiveImbalance")

				key = (dt_utc, negative, positive)
				if key in seen:
					continue
				seen.add(key)

				fetched_data.append(
					{
						"dt_utc": dt_utc,
						"estimatedPriceNegativeImbalance": negative,
						"estimatedPricePositiveImbalance": positive,
					}
				)

		except Exception as ex:
			logger.error("Error fetching data: %s -> fetch_latest_data", ex)
			return []

		return fetched_data

	def store_prices_into_db(self, fetched_data: list[dict[str, Any]]) -> int:
		stored_count = 0

		for data in fetched_data:
			try:
				dt_utc = data.get("dt_utc")
				if dt_utc is None:
					continue

				negative_price = self._normalize_price(data.get("estimatedPriceNegativeImbalance"))
				positive_price = self._normalize_price(data.get("estimatedPricePositiveImbalance"))

				date_utc = dt_utc.date()
				interval_utc = dt_utc.strftime("%H:%M")

				self.db.upsert_imbalance_price(
					date_=date_utc,
					interval=interval_utc,
					positive_imbalance=positive_price,
					negative_imbalance=negative_price,
				)
				stored_count += 1
			except Exception as ex:
				logger.warning(
					"Continue ::: An error occurred when storing prices into the database: %s -> store_prices_into_db",
					ex,
				)

		return stored_count

	def import_latest_prices(self, days_back: int = 3, days_forward: int = 1) -> int:
		fetched_data = self.fetch_latest_data(days_back=days_back, days_forward=days_forward)
		if not fetched_data:
			return 0
		return self.store_prices_into_db(fetched_data)

	@staticmethod
	def _normalize_price(value: Any) -> float:
		if value is None:
			return 0.0
		if isinstance(value, str) and value.strip().upper() == "N/A":
			return 0.0
		return float(value)
