"""Loguru setup: coloured console + one daily-rotated file per process in ``data/logs/``."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS ZZ} | {level: <8} | {name}:{function}:{line} - {message}"
)


def setup_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    process_name: str = "ayvona",
    retention_days: int = 14,
) -> None:
    """Configure the global loguru logger. Safe to call more than once."""
    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT, backtrace=False, diagnose=False)
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / f"{process_name}_{{time:YYYY-MM-DD}}.log",
            level=level,
            format=_FILE_FORMAT,
            rotation="00:00",
            retention=f"{retention_days} days",
            encoding="utf-8",
            backtrace=True,
            diagnose=False,  # never dump local variables (may contain secrets) into files
        )
