from pathlib import Path

from loguru import logger

from ayvona.logging_setup import setup_logging


def test_log_file_created(tmp_path: Path) -> None:
    setup_logging("INFO", log_dir=tmp_path, process_name="test")
    logger.info("salom")
    logger.complete()
    logger.remove()  # release the file handle (Windows)

    files = list(tmp_path.glob("test_*.log"))
    assert len(files) == 1
    assert "salom" in files[0].read_text(encoding="utf-8")
