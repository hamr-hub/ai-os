import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    GREY = "\x1b[38;20m"
    BLUE = "\x1b[34;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    GREEN = "\x1b[32;20m"
    RESET = "\x1b[0m"

    COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED,
    }

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and self._supports_color()
        super().__init__()

    def _supports_color(self) -> bool:
        if os.getenv("NO_COLOR"):
            return False
        if not hasattr(sys.stdout, "isatty"):
            return False
        return sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        module = record.name
        message = record.getMessage()

        if self.use_color:
            color = self.COLORS.get(record.levelno, self.GREY)
            if record.levelno >= logging.ERROR:
                level_str = f"{color}[{level:^8}]{self.RESET}"
            elif record.levelno >= logging.WARNING:
                level_str = f"{color}[{level:^8}]{self.RESET}"
            elif record.levelno >= logging.INFO:
                level_str = f"{self.GREEN}[{level:^8}]{self.RESET}"
            else:
                level_str = f"{self.GREY}[{level:^8}]{self.RESET}"

            return f"{self.GREY}[{timestamp}]{self.RESET} {level_str} {self.BLUE}[{module}]{self.RESET} {message}"
        else:
            return f"[{timestamp}] [{level:^8}] [{module}] {message}"


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] [{record.levelname:^8}] [{record.name}] {record.getMessage()}"


def setup_logger(
    name: str = "ai_controller",
    log_dir: str = None,
    level: int = logging.INFO,
    use_color: bool = True,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(use_color=use_color))
    logger.addHandler(console_handler)

    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(StructuredFormatter())
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "ai_controller") -> logging.Logger:
    return logging.getLogger(name)
