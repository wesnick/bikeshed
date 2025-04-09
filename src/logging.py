from loguru import logger
import sys
import logging
from typing import Dict, Any
from src.config import get_config

app_config = get_config()

class InterceptHandler(logging.Handler):
    """
    Intercept standard logging messages and redirect them to loguru

    This allows us to capture logs from libraries like uvicorn and route them through loguru
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging(config: Dict[str, Any] = None) -> None:
    """
    Configure loguru logger with standard settings

    Args:
        config: Optional configuration dictionary to override defaults
    """
    # Remove default handler
    logger.remove()


    # Configure console output
    logger.add(
        sys.stderr,
        level=app_config.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Add file logging if LOG_FILE is specified in environment
    log_file = app_config.log_file
    if log_file:
        logger.add(
            log_file,
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            level=app_config.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        )

    # Apply any custom configuration
    if config:
        if "extra_handlers" in config:
            for handler in config["extra_handlers"]:
                logger.add(**handler)

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Explicitly intercept uvicorn and FastAPI logs
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    logger.info("Logging configured with level: {}", app_config.log_level)

# Export logger for use in other modules
__all__ = ["logger", "setup_logging"]
