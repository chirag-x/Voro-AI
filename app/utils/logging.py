import logging
import sys

import re

class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt, datefmt):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.patterns = [
            (re.compile(r"(sk-or-v1-[a-zA-Z0-9]{4})[a-zA-Z0-9]+"), r"\1***REDACTED***"),
            (re.compile(r"(Bearer\s+)[a-zA-Z0-9\-\._~+/]+=*"), r"\1***REDACTED***"),
            (re.compile(r"api_key=([a-zA-Z0-9]{4})[a-zA-Z0-9]+"), r"api_key=\1***REDACTED***")
        ]

    def format(self, record):
        message = super().format(record)
        for pattern, replacement in self.patterns:
            message = pattern.sub(replacement, message)
        return message

def setup_logging():
    """Configure centralized logging for the application."""
    logger = logging.getLogger("voro")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = RedactingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

logger = setup_logging()
