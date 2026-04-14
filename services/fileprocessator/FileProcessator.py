import logging
import os
import tempfile
from typing import Iterable, Tuple, Any

from config import DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_TOKEN_FILE, DROPBOX_EVAL_FILE_PATH
from services.dropboxclient.DropboxClient import DropboxClient

logger = logging.getLogger(__name__)


class FileProcessator:
    """
    Skeleton service for processing XLSX files returned by EmailClient.runEmailImport().

    Each item in xlsx_files is expected to be a tuple:
        (file_name, data_bytes, uid, tag, sender_address, email_timestamp)
    """

    def __init__(self) -> None:
        self.xlsx_files: list[Tuple[str, bytes, Any, str, str, Any]] = []
        self.dropbox_client = DropboxClient(
            DROPBOX_APP_KEY,
            DROPBOX_APP_SECRET,
            DROPBOX_TOKEN_FILE,
            DROPBOX_EVAL_FILE_PATH,
        )

    def set_xlsx_files(self, xlsx_files: Iterable[Tuple[str, bytes, Any, str, str, Any]]) -> None:
        self.xlsx_files = list(xlsx_files)

    def process_xlsx_files(self) -> None:
        logging.info("Processing %d XLSX file(s)...", len(self.xlsx_files))

        if not self.xlsx_files:
            return

        dropbox_folder_path = "/mock_uploads"
        for file_name, data, uid, tag, email_address, email_timestamp in self.xlsx_files:
            safe_name = file_name or f"email_{uid}.xlsx"
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{safe_name}") as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            try:
                result = self.dropbox_client.upload_excel_to_dropbox(tmp_path, dropbox_folder_path)
                if result:
                    logger.info("Uploaded %s to Dropbox.", safe_name)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.warning("Could not remove temp file: %s", tmp_path)

        return
