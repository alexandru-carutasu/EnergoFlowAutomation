"""
scheduler-service  —  Background jobs: email import + imbalance price import.
Exposes /health for liveness probes.
Port: 5002
"""
import logging
import os
import sys
from datetime import datetime
from typing import Any, List, Optional

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

sys.path.insert(0, "/app")
from config import (
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_EVAL_FILE_PATH,
    DROPBOX_TOKEN_FILE,
    IMAP_ADDRESS,
    IMAP_PASSWORD,
    IMAP_PORT,
    IMAP_SERVER,
)
from services.emailclient.EmailClient import EmailClient
from services.fileprocessator.FileProcessator import FileProcessator
from services.importclient.ImportClient import ImportClient

logging.basicConfig(
    format="%(levelname)s: [%(asctime)s]:: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %I:%M:%S %p",
)

DB_URL = os.getenv("DB_SERVICE_URL", "http://db-service:5003")

app = Flask(__name__)
metrics = PrometheusMetrics(app)

emailClient = EmailClient(IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD)


# ── HTTP-based DbManager adapter ──────────────────────────────────────────────

class _HttpDbAdapter:
    """
    Adapter that provides DbManager-like interface via HTTP calls to db-service.
    Used by FileProcessator and ImportClient.
    """

    def _parse_date(self, date_str: str):
        return datetime.strptime(date_str, "%Y-%m-%d").date()

    # -- Imbalance prices --

    def upsert_imbalance_price(self, date, interval,
                               positive_imbalance=None, negative_imbalance=None):
        try:
            requests.post(
                f"{DB_URL}/imbalance-prices/upsert",
                json={
                    "date": str(date),
                    "interval": interval,
                    "positive_imbalance": positive_imbalance,
                    "negative_imbalance": negative_imbalance,
                },
                timeout=10,
            )
        except requests.RequestException as e:
            logging.error("Failed to upsert imbalance price: %s", e)

    def get_all_imbalance_prices(self) -> List[Any]:
        """Get all imbalance prices from db-service."""
        try:
            resp = requests.get(f"{DB_URL}/imbalance-prices", timeout=10)
            resp.raise_for_status()
            return [_DictToObj(p) for p in resp.json()]
        except requests.RequestException as e:
            logging.error("Failed to get imbalance prices: %s", e)
            return []

    # -- Plants --

    def get_plants_by_client(self, client_id: int) -> List[Any]:
        """Get plants for a client from db-service."""
        try:
            resp = requests.get(f"{DB_URL}/plants/by-client/{client_id}", timeout=10)
            resp.raise_for_status()
            return [_DictToObj(p) for p in resp.json()]
        except requests.RequestException as e:
            logging.error("Failed to get plants for client %s: %s", client_id, e)
            return []

    # -- Measurements --

    def get_measurements_by_plant_and_date_eager(self, plant_id: int, date) -> List[Any]:
        """Get measurements for a plant and date from db-service."""
        try:
            resp = requests.get(
                f"{DB_URL}/measurements/by-plant-date",
                params={"plant_id": plant_id, "date": str(date)},
                timeout=10,
            )
            resp.raise_for_status()
            return [_DictToObj(m) for m in resp.json()]
        except requests.RequestException as e:
            logging.error("Failed to get measurements for plant %s: %s", plant_id, e)
            return []

    def upsert_measurement(self, plant_id: int, date, interval: int,
                           forecast_val=None, prod_val=None):
        """Upsert a measurement via db-service."""
        try:
            resp = requests.post(
                f"{DB_URL}/measurements/upsert",
                json={
                    "plant_id": plant_id,
                    "date": str(date),
                    "interval": interval,
                    "forecast_val": forecast_val,
                    "prod_val": prod_val,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return _DictToObj(resp.json())
        except requests.RequestException as e:
            logging.error("Failed to upsert measurement: %s", e)
            return None

    # -- Clients --

    def get_client_by_email(self, email: str) -> Optional[Any]:
        """Get client by email from db-service."""
        try:
            resp = requests.get(f"{DB_URL}/clients/by-email/{email}", timeout=10)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _DictToObj(resp.json())
        except requests.RequestException as e:
            logging.error("Failed to get client by email %s: %s", email, e)
            return None

    def add_client(self, name: str, email: str, num_plants: int = 0, has_prod: bool = False):
        """Add a client via db-service."""
        try:
            resp = requests.post(
                f"{DB_URL}/clients",
                json={"name": name, "email": email, "num_plants": num_plants, "has_prod": has_prod},
                timeout=10,
            )
            resp.raise_for_status()
            return _DictToObj(resp.json())
        except requests.RequestException as e:
            logging.error("Failed to add client: %s", e)
            return None


class _DictToObj:
    """Convert dict to object for attribute access (mimics ORM objects)."""
    def __init__(self, d: dict):
        for k, v in d.items():
            setattr(self, k, v)


# Initialize with HTTP adapter
db_adapter = _HttpDbAdapter()
fileProcessator = FileProcessator(db_adapter)


# ── scheduled jobs ────────────────────────────────────────────────────────────

def run_imbalance_import():
    logging.info("Running imbalance import…")
    try:
        importer = ImportClient(db_adapter)
        count = importer.import_latest_prices()
        logging.info("Imported %s imbalance price record(s).", count)
    except Exception as e:
        logging.error("Imbalance import failed: %s", e)


def _download_files(xlsx_files):
    try:
        for (file_name, data, *_rest) in xlsx_files:
            with open(file_name, "wb") as f:
                f.write(data)
    except Exception as e:
        logging.error("Error saving attachments: %s", e)
        return -1
    return len(xlsx_files)


def run_email_import():
    logging.info("Running email import…")
    try:
        emailClient.connect()
        xlsx_files = emailClient.runEmailImport()
        emailClient.disconnect()
    except Exception as e:
        logging.error("Email import failed: %s", e)
        return

    if not xlsx_files:
        logging.info("No new email attachments.")
        return

    nr = _download_files(xlsx_files)
    if nr == -1:
        return
    logging.info("Downloaded %s file(s) from email.", nr)

    fileProcessator.set_xlsx_files(xlsx_files)
    fileProcessator.process_xlsx_files()


# ── health ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_imbalance_import, trigger="interval", minutes=15, max_instances=1)
    scheduler.add_job(run_email_import, trigger="interval", minutes=10, max_instances=1)
    scheduler.start()
    logging.info("Scheduler started.")
    app.run(host="0.0.0.0", port=5002)
