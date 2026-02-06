"""
Logging infrastructure for Sassy Wallet.

Provides decorators and utilities for structured exception logging without
exposing sensitive information or stack traces to the user.
"""
import logging
import functools
import traceback
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Callable, TypeVar, Any, Optional
from pathlib import Path

# Type variable for generic function decoration
F = TypeVar('F', bound=Callable[..., Any])
_PRIVATE_FILE_MODE = 0o600
_PRIVATE_DIR_MODE = 0o700
_TEZOS_ADDR_RE = re.compile(r"\b(?:tz[1-4]|KT1)[1-9A-HJ-NP-Za-km-z]{33}\b")
_TEZOS_OPH_RE = re.compile(r"\bo[1-9A-HJ-NP-Za-km-z]{50}\b")
_TEZOS_SK_RE = re.compile(r"\b(?:edsk|edesk)[1-9A-HJ-NP-Za-km-z]{20,}\b")
_TEZOS_SIG_RE = re.compile(r"\bsig[1-9A-HJ-NP-Za-km-z]{20,}\b")
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{64,}\b")


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except (OSError, PermissionError):
        return


def redact_sensitive_text(text: str) -> str:
    """Redact common sensitive blockchain values from logs."""
    if not text:
        return text
    redacted = str(text)
    redacted = _TEZOS_ADDR_RE.sub("<tezos-address:redacted>", redacted)
    redacted = _TEZOS_OPH_RE.sub("<operation-hash:redacted>", redacted)
    redacted = _TEZOS_SK_RE.sub("<secret-key:redacted>", redacted)
    redacted = _TEZOS_SIG_RE.sub("<signature:redacted>", redacted)
    redacted = _LONG_HEX_RE.sub("<hex:redacted>", redacted)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(_redact_value(v) for v in value)
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    if isinstance(value, set):
        return {_redact_value(v) for v in value}
    return value


class _RedactingFilter(logging.Filter):
    """Filter that redacts sensitive values from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_value(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_value(v) for v in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _redact_value(v) for k, v in record.args.items()}
        return True


class _SecureRotatingFileHandler(RotatingFileHandler):
    """Rotating handler that enforces private file permissions."""

    def _open(self):
        stream = super()._open()
        _chmod_best_effort(Path(self.baseFilename), _PRIVATE_FILE_MODE)
        return stream

    def doRollover(self) -> None:
        super().doRollover()
        _chmod_best_effort(Path(self.baseFilename), _PRIVATE_FILE_MODE)
        for i in range(1, self.backupCount + 1):
            _chmod_best_effort(Path(f"{self.baseFilename}.{i}"), _PRIVATE_FILE_MODE)


def setup_logger(name: str = "wallet", log_file: str = "logs/wallet.log", level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with file and console handlers.

    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        if not any(isinstance(f, _RedactingFilter) for f in logger.filters):
            logger.addFilter(_RedactingFilter())
        return logger

    logger.setLevel(level)

    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True, mode=_PRIVATE_DIR_MODE)
    _chmod_best_effort(log_path.parent, _PRIVATE_DIR_MODE)

    # File handler with rotation
    file_handler = _SecureRotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.addFilter(_RedactingFilter())
    _chmod_best_effort(log_path, _PRIVATE_FILE_MODE)
    for i in range(1, file_handler.backupCount + 1):
        _chmod_best_effort(Path(f"{log_file}.{i}"), _PRIVATE_FILE_MODE)
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    logger.addFilter(_RedactingFilter())

    # Prevent propagation to root logger (which might have StreamHandler)
    logger.propagate = False

    return logger


# Global logger instance
_logger = setup_logger()


def get_logger() -> logging.Logger:
    """Get the global wallet logger instance."""
    return _logger


def _format_wrapped_exception_message(
    *,
    user_message: str,
    func_name: str,
    exception: BaseException,
    arg_count: int,
    kwarg_count: int,
) -> str:
    return (
        f"{user_message}: {type(exception).__name__}: {str(exception)}\n"
        f"Function: {func_name}\n"
        f"ArgCount: {arg_count} Positional, {kwarg_count} Keyword\n"
        f"Traceback:\n{traceback.format_exc()}"
    )


def _format_exception_traceback(exception: BaseException | None = None) -> str:
    if exception and exception.__traceback__:
        return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    return traceback.format_exc()


def log_exception(
    user_message: str = "An error occurred",
    log_level: int = logging.ERROR,
    reraise: bool = True
) -> Callable[[F], F]:
    """
    Decorator that logs exceptions with full context while showing user-friendly messages.

    This decorator:
    1. Catches all exceptions
    2. Logs them with full traceback to the log file
    3. Optionally re-raises them (default) or swallows them

    Args:
        user_message: Friendly message shown to user (no stack trace)
        log_level: Logging level for the exception
        reraise: If True, re-raise the exception after logging

    Usage:
        @log_exception("Failed to load wallet")
        def load_wallet(path: str):
            # ... code that might fail ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log full exception with traceback to file
                logger = get_logger()
                logger.log(
                    log_level,
                    _format_wrapped_exception_message(
                        user_message=user_message,
                        func_name=func.__name__,
                        exception=e,
                        arg_count=len(args),
                        kwarg_count=len(kwargs),
                    )
                )

                if reraise:
                    raise
                else:
                    # Return None or appropriate default for swallowed exceptions
                    return None

        return wrapper  # type: ignore[return-value]

    return decorator


def safe_log_exception(
    default_return: Any = None,
    user_message: str = "Operation failed",
    log_level: int = logging.ERROR
) -> Callable[[F], F]:
    """
    Decorator that logs exceptions and returns a default value instead of crashing.

    This is useful for non-critical operations where you want graceful degradation.

    Args:
        default_return: Value to return if exception occurs
        user_message: Friendly message for logs
        log_level: Logging level

    Usage:
        @safe_log_exception(default_return=[], user_message="Failed to fetch history")
        def get_history(address: str) -> list:
            # ... code that might fail ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log full exception
                logger = get_logger()
                logger.log(
                    log_level,
                    _format_wrapped_exception_message(
                        user_message=user_message,
                        func_name=func.__name__,
                        exception=e,
                        arg_count=len(args),
                        kwarg_count=len(kwargs),
                    )
                )

                # Return default value
                return default_return

        return wrapper  # type: ignore[return-value]

    return decorator


def log_info(message: str, **context: Any) -> None:
    """Log an info message with optional context."""
    logger = get_logger()
    if context:
        logger.info(f"{message} | Context: {context}")
    else:
        logger.info(message)


def log_warning(message: str, **context: Any) -> None:
    """Log a warning message with optional context."""
    logger = get_logger()
    if context:
        logger.warning(f"{message} | Context: {context}")
    else:
        logger.warning(message)


def log_error(message: str, exception: Optional[BaseException] = None, **context: Any) -> None:
    """
    Log an error message with optional exception and context.

    Args:
        message: Error message
        exception: Optional exception to log
        context: Additional context as keyword arguments
    """
    logger = get_logger()
    msg = message

    if exception:
        msg += f" | Exception: {type(exception).__name__}: {str(exception)}"

    if context:
        msg += f" | Context: {context}"

    logger.error(msg)

    if exception:
        logger.debug(f"Traceback:\n{_format_exception_traceback(exception)}")


def log_debug(message: str, **context: Any) -> None:
    """Log a debug message with optional context."""
    logger = get_logger()
    if context:
        logger.debug(f"{message} | Context: {context}")
    else:
        logger.debug(message)
