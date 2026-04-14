"""Logging configuration with daily rotating file handler."""

from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logging(name: str, log_directory: str = "./logs", level: int = logging.DEBUG) -> logging.Logger:
    """Set up a logger with console and daily rotating file handler.

    Args:
        name: Logger name (e.g. 'bot' or 'monitoring').
        log_directory: Directory for log files.
        level: Logging level.

    Returns:
        Configured logger instance.
    """
    os.makedirs(log_directory, exist_ok=True)
    log_file = os.path.join(log_directory, f"{name}.log")

    log_logger = logging.getLogger(name)
    log_logger.setLevel(level)

    # Avoid duplicate handlers on reload
    if log_logger.handlers:
        return log_logger

    # File handler: rotate daily, keep 7 days
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=7,
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Configure root logger so all modules (including libraries) log properly.
    # The named logger inherits from root, so we don't add handlers to it
    # directly -- that would cause duplicate lines.
    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(level)
        root.addHandler(file_handler)
        root.addHandler(console_handler)

    return log_logger
