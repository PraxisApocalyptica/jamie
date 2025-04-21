import logging


# --- Custom Severity Formatter ---
class SeverityHandler(logging.Formatter):
    """
    A custom formatter that adds a symbol based on the log level
    at the beginning of the message part.
    """
    # Define symbols for specific levels
    LEVEL_SYMBOLS = {
        logging.DEBUG: '',        # Optional: Symbol for DEBUG
        logging.INFO: '✅ ',     # Symbol for INFO with a space after
        logging.WARNING: '❗ ',  # Optional: Symbol for WARNING
        logging.ERROR: '🚨 ',    # Symbol for ERROR with a space after
        logging.CRITICAL: '💥 '  # Symbol for CRITICAL with a space after
    }

    def __init__(self, fmt=None, datefmt=None, style='%'):
        # Store the original format string
        self._original_fmt = fmt if fmt else logging.BASIC_FORMAT
        super().__init__(fmt, datefmt, style)

    def format(self, record):
        # Get the symbol for the current log level, default to empty string
        symbol = self.LEVEL_SYMBOLS.get(record.levelno, '')

        # Create a copy of the record to avoid modifying the original record
        # which might be processed by other handlers/formatters.
        record_copy = logging.makeLogRecord(record.__dict__)

        # Prepend the symbol to the message *in the copy*
        # This way, the symbol appears before the message text when the
        # %(message)s part of the format string is processed.
        # Clear args because we're embedding them into the message string directly
        # by modifying record_copy.msg
        record_copy.msg = f"{symbol}{record_copy.getMessage()}" # Use getMessage() to handle % args
        record_copy.args = () # Clear args as they are now part of the message string

        # Format the modified record copy using the parent formatter
        return super().format(record_copy)
