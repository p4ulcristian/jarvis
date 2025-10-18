"""
Logging configuration for JARVIS
Provides structured logging with proper levels and formatting
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    debug: bool = False,
    log_file: Optional[str] = None,
    name: str = 'jarvis'
) -> logging.Logger:
    """
    Configure logging for JARVIS

    Args:
        debug: Enable debug logging
        log_file: Optional file path for logging
        name: Logger name

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger('nemo_logger').setLevel(logging.ERROR)
    logging.getLogger('pytorch_lightning').setLevel(logging.ERROR)
    logging.getLogger('torch').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    return logger


def get_logger(name: str = 'jarvis') -> logging.Logger:
    """
    Get logger instance

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
