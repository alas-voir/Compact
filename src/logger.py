import io
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from .paths import user_config_dir

_LOGGER_INITIALIZED = False
_LOG_FILE_PATH: Path | None = None


class _TeeStream(io.TextIOBase):
    def __init__(self, logger: logging.Logger, level: int, original_stream) -> None:
        super().__init__()
        self._logger = logger
        self._level = level
        self._original_stream = original_stream
        self._buffer = ""

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            text = str(text)
        if self._original_stream is not None:
            try:
                self._original_stream.write(text)
            except Exception:
                pass
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self._logger.log(self._level, line)
        return len(text)

    def flush(self) -> None:
        if self._original_stream is not None:
            try:
                self._original_stream.flush()
            except Exception:
                pass
        line = self._buffer.strip()
        if line:
            self._logger.log(self._level, line)
        self._buffer = ""


def app_log_path() -> Path:
    global _LOG_FILE_PATH
    if _LOG_FILE_PATH is None:
        logs_dir = user_config_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        _LOG_FILE_PATH = logs_dir / "compact.log"
    return _LOG_FILE_PATH


def get_logger(name: str = "compact") -> logging.Logger:
    return logging.getLogger(name)


def _install_exception_hook(logger: logging.Logger) -> None:
    original_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_traceback) -> None:
        logger.exception(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        if original_hook is not None:
            original_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _hook


def setup_app_logging() -> Path:
    global _LOGGER_INITIALIZED
    if _LOGGER_INITIALIZED:
        return app_log_path()

    log_path = app_log_path()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=1_500_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)

    logger = get_logger("compact")
    _install_exception_hook(logger)

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _TeeStream(get_logger("compact.stdout"), logging.INFO, original_stdout)
    sys.stderr = _TeeStream(get_logger("compact.stderr"), logging.ERROR, original_stderr)

    logger.info("Logging initialized")
    logger.info("Log file: %s", log_path)
    logger.info(
        "Runtime | frozen=%s | executable=%s | cwd=%s | pid=%s | python=%s | platform=%s",
        getattr(sys, "frozen", False),
        sys.executable,
        os.getcwd(),
        os.getpid(),
        sys.version.replace("\n", " "),
        sys.platform,
    )
    _LOGGER_INITIALIZED = True
    return log_path
