import logging
import os

from typing import Optional
from logging.handlers import RotatingFileHandler
from datetime import datetime
from src.handlers.severity_handler import SeverityHandler


class LogHandler:
    """
    Handles centralized logging configuration for the application.
    Configures root logger with console and rotating file handlers,
    using a custom formatter to add symbols.
    """
    def __init__(self):
        self._logger_instance = logging.getLogger()
        self._configured = False
        self.configure_logging()

    def configure_logging(self, log_dir="../logs", log_prefix="robot", max_bytes=5*1024*1024, backup_count=5):
        """Configures the root logger with console and file handlers using SymbolFormatter."""
        if self._configured:
            self._logger_instance.warning("LogHandler is already configured. Skipping.")
            return

        # Clear existing handlers from the root logger to avoid duplicates
        for handler in list(self._logger_instance.handlers):
            self._logger_instance.removeHandler(handler)

        self._logger_instance.setLevel(logging.DEBUG) # Set root logger level

        # Define the format string for both handlers
        # The SymbolFormatter will prepend the symbol *within* the %(message)s part
        # So the symbol will appear like: "LOGGERNAME - LEVELNAME - ✅ Your info message"
        # Or "LOGGERNAME - LEVELNAME - 🚨 Your error message"
        console_log_format = '%(name)s - %(levelname)s - %(message)s'
        file_log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


        # Create the SymbolFormatter instances
        # You can customize symbols or format strings per handler if needed
        console_formatter = SeverityHandler(fmt=console_log_format)
        file_formatter = SeverityHandler(fmt=file_log_format)


        # Console handler (INFO+)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO) # Console shows INFO, ERROR, CRITICAL
        console_handler.setFormatter(console_formatter)
        self._logger_instance.addHandler(console_handler)

        # File handler (DEBUG+)
        try:
            os.makedirs(log_dir, exist_ok=True)
            current_date = datetime.now().strftime("%d-%m-%Y")
            log_file_path = os.path.join(log_dir, f"{log_prefix}-{current_date}.log")

            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8' # Ensure symbols are handled correctly
            )
            file_handler.setLevel(logging.DEBUG) # File shows DEBUG and above
            file_handler.setFormatter(file_formatter)
            self._logger_instance.addHandler(file_handler)

            self._logger_instance.debug(f"Logging to file: {log_file_path}")
        except Exception as e:
            self._logger_instance.error(f"🚨 Could not set up RotatingFileHandler: {e}. Logging to console only.") # Using symbol here manually as handler might not be added yet

        self._configured = True

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        Returns a logger instance. If name is None, returns the root logger.
        Otherwise, returns a child logger.
        """
        if name is None:
            return self._logger_instance
        else:
            return self._logger_instance.getChild(name)
