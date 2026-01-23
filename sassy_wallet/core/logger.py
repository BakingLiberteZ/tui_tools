"""
Logging infrastructure for Sassy Wallet.

Provides decorators and utilities for structured exception logging without
exposing sensitive information or stack traces to the user.
"""
import logging
import functools
import traceback
from typing import Callable, TypeVar, Any, Optional
from pathlib import Path

# Type variable for generic function decoration
F = TypeVar('F', bound=Callable[..., Any])


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
        return logger

    logger.setLevel(level)

    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler with rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger (which might have StreamHandler)
    logger.propagate = False

    return logger


# Global logger instance
_logger = setup_logger()


def get_logger() -> logging.Logger:
    """Get the global wallet logger instance."""
    return _logger


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
                    f"{user_message}: {type(e).__name__}: {str(e)}\n"
                    f"Function: {func.__name__}\n"
                    f"Args: {args[:2] if args else 'none'}...\n"  # Limit args to avoid logging sensitive data
                    f"Traceback:\n{traceback.format_exc()}"
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
                    f"{user_message}: {type(e).__name__}: {str(e)}\n"
                    f"Function: {func.__name__}\n"
                    f"Args: {args[:2] if args else 'none'}...\n"
                    f"Traceback:\n{traceback.format_exc()}"
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


def log_error(message: str, exception: Optional[Exception] = None, **context: Any) -> None:
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
        logger.debug(f"Traceback:\n{traceback.format_exc()}")


def log_debug(message: str, **context: Any) -> None:
    """Log a debug message with optional context."""
    logger = get_logger()
    if context:
        logger.debug(f"{message} | Context: {context}")
    else:
        logger.debug(message)
