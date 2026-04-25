"""
migrate.py  –  Database migration / bootstrap script for EnergoFlow.

What it does
------------
1. Connects to MySQL server (without specifying a database)
2. Creates the database if it doesn't already exist
3. Creates all tables defined in the ORM models
4. Prints a summary of what was created

Usage
-----
    python migrate.py              # run standalone
    python migrate.py --drop       # drop all tables first, then recreate (DEV ONLY)
"""

import sys
import logging

import pymysql
from sqlalchemy import inspect

from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DATABASE_URL
from services.dbmanager.DbManager import DbManager
from services.dbmanager.models import Base

logging.basicConfig(
    format="%(levelname)s: [%(asctime)s]:: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %I:%M:%S %p",
)
logger = logging.getLogger(__name__)


def ensure_database_exists() -> None:
    """Connect to MySQL server and CREATE DATABASE IF NOT EXISTS."""
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            logger.info("✅  Database '%s' ensured.", DB_NAME)
    finally:
        conn.close()


def run_migration(drop_first: bool = False) -> None:
    """Full migration: ensure DB → (optional drop) → create tables."""
   
    ensure_database_exists()

    
    db = DbManager(DATABASE_URL)

    
    if drop_first:
        logger.warning(" Dropping ALL tables (--drop flag detected)...")
        db.drop_tables()

   
    db.create_tables()

    # Step 5 – summary
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    logger.info("📋  Tables in '%s': %s", DB_NAME, ", ".join(tables) if tables else "(none)")
    for t in tables:
        cols = [c["name"] for c in inspector.get_columns(t)]
        logger.info("    ├─ %-20s  columns: %s", t, ", ".join(cols))

    logger.info(" Migration complete – %d table(s) ready.", len(tables))
    return db


if __name__ == "__main__":
    drop = "--drop" in sys.argv
    run_migration(drop_first=drop)
