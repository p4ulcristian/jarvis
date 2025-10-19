"""
Logging configuration for JARVIS
Provides structured logging with proper levels and formatting
"""
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def setup_logging(
    debug: bool = False,
    log_file: Optional[str] = None,
    name: str = 'jarvis',
    data_bridge: Optional['DataBridge'] = None
) -> logging.Logger:
    """
    Configure logging for JARVIS

    Args:
        debug: Enable debug logging
        log_file: Optional file path for logging (defaults to ~/.jarvis/logs/jarvis_YYYYMMDD.log)
        name: Logger name
        data_bridge: Optional DataBridge for UI logging

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

    # UI handler (when data_bridge is available)
    if data_bridge:
        # Import UILogHandler here to avoid circular imports at module load time
        try:
            from ui.data_bridge import UILogHandler
            ui_handler = UILogHandler(data_bridge)
            ui_handler.setLevel(logging.DEBUG if debug else logging.INFO)
            # Use simple formatter for UI (no timestamp - UI adds its own)
            ui_formatter = logging.Formatter(fmt='%(message)s')
            ui_handler.setFormatter(ui_formatter)
            logger.addHandler(ui_handler)
        except ImportError as e:
            # Fallback if ui module not available yet
            pass

    # File handler (always enabled for persistent logs)
    if not log_file:
        # Default log file location
        log_dir = Path.home() / '.jarvis' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / f"jarvis_{datetime.now().strftime('%Y%m%d')}.log")

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
