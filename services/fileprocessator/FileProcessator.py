import logging
from typing import Iterable, Tuple, Any

logger = logging.getLogger(__name__)


class FileProcessator:
    """
    Skeleton service for processing XLSX files returned by EmailClient.runEmailImport().

    Each item in xlsx_files is expected to be a tuple:
        (file_name, data_bytes, uid, tag, sender_address, email_timestamp)
    """

    def __init__(self) -> None:
        self.xlsx_files: list[Tuple[str, bytes, Any, str, str, Any]] = []

    def set_xlsx_files(self, xlsx_files: Iterable[Tuple[str, bytes, Any, str, str, Any]]) -> None:
        self.xlsx_files = list(xlsx_files)

    def process_xlsx_files(self) -> None:
        logging.info(f"Processing {len(self.xlsx_files)} XLSX file(s)...")
        return
