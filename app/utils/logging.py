import logging
import sys
import os
from logging.handlers import RotatingFileHandler
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
        formatter = RedactingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        try:
            log_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "voro.log")
            
            file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Fallback if we can't write to the logs directory
            print(f"Warning: Could not setup file logging: {e}")

    return logger

logger = setup_logging()
