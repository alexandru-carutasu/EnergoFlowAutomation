"""
scheduler-service  —  Background jobs: email import + imbalance price import.
Exposes /health for liveness probes.
Port: 5002
"""
import logging
import os
import sys

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
fileProcessator = FileProcessator()


# ── DB adapter (lets ImportClient call db-service via HTTP) ───────────────────

class _HttpDbAdapter:
    """Thin adapter that gives ImportClient a db-compatible upsert interface."""

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


# ── scheduled jobs ────────────────────────────────────────────────────────────

def run_imbalance_import():
    logging.info("Running imbalance import…")
    try:
        importer = ImportClient(_HttpDbAdapter())
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
