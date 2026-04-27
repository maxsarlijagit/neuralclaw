"""Structured logging with Rich."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

import appdirs

# Custom theme for NeuralClaw
CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "debug": "dim",
    "success": "bold green",
})


class RichConsole(Console):
    """Rich console with NeuralClaw theme."""
    pass


console = RichConsole(theme=CUSTOM_THEME)


def get_log_dir() -> Path:
    """Get NeuralClaw log directory."""
    log_dir = Path(appdirs.user_log_dir("neuralclaw"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_file() -> Path:
    """Get the main log file path."""
    return get_log_dir() / "neuralclaw.log"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    enable_rich: bool = True,
) -> logging.Logger:
    """Configure structured logging with Rich and file output."""
    logger = logging.getLogger("neuralclaw")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    log_path = log_file or get_log_file()

    # File handler — structured text format
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler — Rich
    if enable_rich:
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            show_time=True,
            show_path=False,
        )
    else:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(file_formatter)
        rich_handler = stream_handler

    logger.addHandler(file_handler)
    logger.addHandler(rich_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance for a module."""
    logger = logging.getLogger("neuralclaw" + (f".{name}" if name else ""))
    return logger


# ─── Command Logging Helpers ──────────────────────────────────────────────────

from contextlib import contextmanager
from typing import Optional
import time


@contextmanager
def log_command(
    action: str,
    project_id: Optional[str] = None,
):
    """Context manager to log command start/end with duration."""
    logger = get_logger()
    start = time.time()
    logger.info(f"CMD {action} | project={project_id or 'global'}")

    try:
        yield
    except Exception as e:
        duration = time.time() - start
        logger.error(f"CMD {action} FAILED ({duration:.2f}s) | {e}")
        raise
    else:
        duration = time.time() - start
        logger.info(f"CMD {action} OK ({duration:.2f}s)")


def log_info(message: str):
    """Log an info message."""
    get_logger().info(message)


def log_warning(message: str):
    """Log a warning message."""
    get_logger().warning(message)


def log_error(message: str):
    """Log an error message."""
    get_logger().error(message)


def log_debug(message: str):
    """Log a debug message."""
    get_logger().debug(message)


def init_logging(level: str = "INFO"):
    """Initialize logging at startup."""
    import os
    # Check for DEBUG env var
    if os.environ.get("NEURALCLAW_DEBUG"):
        level = "DEBUG"
    return setup_logging(level=level)
