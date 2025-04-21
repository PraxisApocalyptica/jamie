import logging
import os

from logging.handlers import RotatingFileHandler
from datetime import datetime


class LogHandler:
    def __init__(self, log_dir="../logs", log_prefix="robot", max_bytes=5*1024*1024, backup_count=5):
        self.log_dir = log_dir
        self.log_prefix = log_prefix
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._logger = logging.getLogger()
        self.configure_logging()

    def configure_logging(self):
        # Clear existing handlers
        self._logger.handlers.clear()
        self._logger.setLevel(logging.DEBUG)

        # Console handler (INFO+)
        console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        self._logger.addHandler(console_handler)

        # File handler (DEBUG+)
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            current_date = datetime.now().strftime("%d-%m-%Y")
            log_file_path = os.path.join(self.log_dir, f"{self.log_prefix}-{current_date}.log")

            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            self._logger.addHandler(file_handler)

            self._logger.info(f"Logging to file: {log_file_path}")
        except Exception as e:
            self._logger.error(f"Could not set up RotatingFileHandler: {e}. Logging to console only.")

    def get_logger(self):
        return self._logger
