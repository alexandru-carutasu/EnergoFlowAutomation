from dotenv import load_dotenv
import os

load_dotenv()


# Constants
PORT = 5000
PROCESSING_TAG = 0
DONE_TAG = 1

IBD_TAG = 0
FORECAST_TAG = 1

IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT"))

IMAP_ADDRESS = os.getenv("IMAP_ADDRESS")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

FORECAST_ADDRESS = os.getenv("FORECAST_ADDRESS")

# ── Database ───────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "energoflow")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)