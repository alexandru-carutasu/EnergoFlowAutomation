import logging
import os
import tempfile
import datetime
import pytz
import time
import imaplib
from typing import Iterable, Tuple, Any, Optional
from openpyxl import load_workbook
from datetime import datetime as dt, timedelta

from config import (
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_TOKEN_FILE,
    DROPBOX_EVAL_FILE_PATH,
    PROCESSING_TAG,
    DONE_TAG,
    IBD_TAG,
    FORECAST_TAG,
    IMAP_SERVER,
    IMAP_USER,
    IMAP_PASSWORD,
)
from services.dropboxclient.DropboxClient import DropboxClient
from services.dbmanager.DbManager import DbManager
from services.fileprocessator.EvalFileManager import EvalFileManager

logger = logging.getLogger(__name__)


class FileProcessator:
    """
    Advanced service for processing XLSX files with database integration.

    Each item in xlsx_files is expected to be a tuple:
        (file_name, payload, curr_email, tag, sender, email_timestamp, client_name)
    """

    def __init__(self, db_manager: DbManager) -> None:
        """Initialize FileProcessator with database and Dropbox clients."""
        self.xlsx_files: list[Tuple[str, bytes, Any, str, str, Any, str]] = []
        self.db_manager = db_manager
        self.dropbox_client = DropboxClient(
            DROPBOX_APP_KEY,
            DROPBOX_APP_SECRET,
            DROPBOX_TOKEN_FILE,
            DROPBOX_EVAL_FILE_PATH,
        )
        self.eval_file_manager = EvalFileManager(db_manager, self.dropbox_client)

    def set_xlsx_files(
        self, xlsx_files: Iterable[Tuple[str, bytes, Any, str, str, Any, str]]
    ) -> None:
        """Set XLSX files for processing."""
        self.xlsx_files = list(xlsx_files)

    def process_xlsx_files(self) -> None:
        """Process all XLSX files through the complete workflow."""
        logging.info("Processing %d XLSX file(s)...", len(self.xlsx_files))

        if not self.xlsx_files:
            return

        for file_name, payload, curr_email, tag, sender, email_timestamp, client_name in self.xlsx_files:
            try:
                self._process_single_file(
                    file_name, payload, curr_email, tag, sender, email_timestamp, client_name
                )
            except Exception as e:
                logging.error(f"Error processing file {file_name}: {e}", exc_info=True)

    def _process_single_file(
        self,
        file_name: str,
        payload: bytes,
        curr_email: Any,
        tag: str,
        sender: str,
        email_timestamp: Any,
        client_name: str,
    ) -> None:
        """Process a single XLSX file through the complete workflow."""
        local_file_path = file_name
        with open(local_file_path, "wb") as f:
            f.write(payload)

        try:
            # Store measurements in database with tag
            result = self._store_measurements_into_db(local_file_path, client_name, tag)
            if result:
                logging.error(f"Failed to store measurements: {result}")
        except Exception as e:
            logging.error(f"Error processing file {file_name}: {e}", exc_info=True)
        finally:
            try:
                os.remove(local_file_path)
            except OSError:
                pass

    def _store_measurements_into_db(
        self, file_path: str, client_name: str, tag: str
    ) -> str:
        """Store measurements from XLSX into database with tag support."""
        logging.info("Storing measurements...")
        try:
            workbook, header, forecast_idx = self._load_workbook_and_header(file_path)
            if workbook is None:
                return "ERROR"

            for sheet_name in workbook.sheetnames:
                error = self._process_sheet_rows(
                    workbook, sheet_name, client_name, header, forecast_idx, tag
                )
                if error:
                    return error

            return ""
        except Exception as e:
            logging.error(f"Error storing measurements: {e}")
            return "ERROR"

    def _load_workbook_and_header(self, file_path: str) -> Tuple[Any, dict, Optional[int]]:
        """Load workbook and extract header with forecast column index."""
        try:
            workbook = load_workbook(file_path)
            sheet_names = workbook.sheetnames
            if not sheet_names:
                raise ValueError("No sheets found in workbook")

            # Access first sheet for header
            sheet = workbook[sheet_names[0]]
            header = {cell.value: idx for idx, cell in enumerate(sheet[1])}

            # Find forecast column
            forecast_idx = self._find_forecast_column(header)
            if forecast_idx is None:
                raise ValueError("Forecast column not found in sheet")

            return workbook, header, forecast_idx
        except Exception as e:
            logging.error(f"Error loading workbook: {e}")
            return None, {}, None

    def _find_forecast_column(self, header: dict) -> Optional[int]:
        """Find forecast column index from header row."""
        forecast_column_names = ["P FINAL", "Prognoza la 15 minute", "PROGNOZA"]
        for col_name in forecast_column_names:
            if col_name in header:
                return header[col_name]
        return None

    def _process_sheet_rows(
        self,
        workbook: Any,
        sheet_name: str,
        client_name: str,
        header: dict,
        forecast_idx: int,
        tag: str,
    ) -> str:
        """Process all rows in a sheet and store measurements."""
        try:
            logging.info(f"Processing sheet: {sheet_name}")

            measurements_batch = []
            prev_date = None

            for row in workbook[sheet_name].iter_rows(min_row=2, values_only=True):
                if not row[0]:
                    continue

                measurements, date = self._parse_row_and_add_measurements(
                    row, header, forecast_idx, tag
                )
                if measurements:
                    measurements_batch.extend(measurements)

                # Batch insert when date changes
                if date and date != prev_date and measurements_batch:
                    logging.debug(f"Batch insert: {len(measurements_batch)} measurements")
                    measurements_batch = []
                    prev_date = date
                    time.sleep(0.2)

            # Final batch insert
            if measurements_batch:
                logging.debug(f"Final batch insert: {len(measurements_batch)} measurements")

            return ""
        except Exception as e:
            logging.error(f"Error processing sheet {sheet_name}: {e}")
            return "SHEET_ERROR"

    def _parse_row_and_add_measurements(
        self, row: Tuple, header: dict, forecast_idx: int, tag: str
    ) -> Tuple[list, Optional[Any]]:
        """Parse a single row and create measurement entries with tag-based column selection."""
        try:
            date = row[header.get("ZIUA", 0)]
            hour_interval = row[header.get("INTERVAL", 1)]
            data_value = row[forecast_idx]

            if not date or not hour_interval:
                return [], None

            intervals = self._parse_time_intervals(hour_interval)
            measurements = []

            for interval_start in intervals:
                # Unified storage: use tag to determine which column to populate
                if tag == FORECAST_TAG:
                    measurement = {
                        "date": date,
                        "interval": interval_start,
                        "forecast_val": data_value,
                    }
                elif tag == IBD_TAG:
                    measurement = {
                        "date": date,
                        "interval": interval_start,
                        "prod_val": data_value,
                    }
                else:
                    logging.warning(f"Unknown tag: {tag}. Skipping.")
                    continue

                measurements.append(measurement)

            return measurements, date
        except Exception as e:
            logging.error(f"Error parsing row: {e}")
            return [], None

    def _parse_time_intervals(self, hour_interval: str) -> list[str]:
        """Parse time interval string and split into 15-minute intervals."""
        try:
            start_hour, end_hour = hour_interval.split("-")
            start_time = dt.strptime(start_hour.strip(), "%H:%M")
            end_time = dt.strptime(end_hour.strip(), "%H:%M")

            # Split 1-hour intervals into four 15-minute intervals
            if (end_time - start_time).seconds == 3600:
                intervals = [
                    (start_time + timedelta(minutes=15 * i)).strftime("%H:%M") for i in range(4)
                ]
            else:
                intervals = [start_time.strftime("%H:%M")]

            return intervals
        except Exception as e:
            logging.error(f"Error parsing time intervals: {e}")
            return []

    def _create_evaluation_file(self, client_id: int, client_name: str, date_str: str) -> None:
        """Create evaluation file via EvalFileManager."""
        try:
            self.eval_file_manager.create_evaluation_file(client_id, client_name, date_str)
            logging.info(f"Created evaluation file for {client_name} on {date_str}")
        except Exception as e:
            logging.error(f"Error creating evaluation file: {e}")

    def _update_evaluation_files(self, client_name: str, client_id: int, curr_date: Any) -> None:
        """Update evaluation files via EvalFileManager."""
        try:
            self.eval_file_manager.update_evaluation_files(client_name, client_id, curr_date)
            logging.info(f"Updated evaluation files for {client_name}")
        except Exception as e:
            logging.error(f"Error updating evaluation files: {e}")

    def _update_evaluation_file(self, client_name: str, client_id: int, curr_date: Any) -> None:
        """Update single evaluation file via EvalFileManager."""
        try:
            self.eval_file_manager.update_evaluation_files_1plant(client_name, client_id, curr_date)
            logging.info(f"Updated evaluation file for {client_name}")
        except Exception as e:
            logging.error(f"Error updating evaluation file: {e}")

    def _update_evaluation_files_1plant(self, client_name: str, client_id: int, curr_date: Any) -> None:
        """Update evaluation files for single plant via EvalFileManager."""
        try:
            self.eval_file_manager.update_evaluation_files_1plant(client_name, client_id, curr_date)
            logging.info(f"Updated plant evaluation for {client_name}")
        except Exception as e:
            logging.error(f"Error updating plant evaluation: {e}")

    def _del_email(self, uid: int) -> None:
        """Delete email by UID using IMAP."""
        try:
            # Convert UID to bytes if needed
            uid_str = str(uid).encode() if isinstance(uid, int) else uid

            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(IMAP_USER, IMAP_PASSWORD)
            mail.select("INBOX")

            # Mark email as deleted
            mail.store(uid_str, "+FLAGS", "\\Deleted")
            mail.expunge()
            mail.close()
            mail.logout()

            logging.info(f"Deleted email with UID {uid}")
        except Exception as e:
            logging.error(f"Error deleting email {uid}: {e}")
