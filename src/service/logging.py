from loguru import logger
import sys
import os
from typing import Dict, Any

def setup_logging(config: Dict[str, Any] = None) -> None:
    """
    Configure loguru logger with standard settings
    
    Args:
        config: Optional configuration dictionary to override defaults
    """
    # Remove default handler
    logger.remove()
    
    # Get log level from environment or use INFO as default
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    
    # Configure console output
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    
    # Add file logging if LOG_FILE is specified in environment
    log_file = os.environ.get("LOG_FILE")
    if log_file:
        logger.add(
            log_file,
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        )
    
    # Apply any custom configuration
    if config:
        if "extra_handlers" in config:
            for handler in config["extra_handlers"]:
                logger.add(**handler)
    
    logger.info("Logging configured with level: {}", log_level)

# Export logger for use in other modules
__all__ = ["logger", "setup_logging"]
