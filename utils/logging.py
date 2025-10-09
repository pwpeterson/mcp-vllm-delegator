"""
Logging utilities and setup
"""

import logging
import os
import sys
from pathlib import Path


def setup_logging(config=None):
    """Setup logging based on configuration"""

    if config and config.logging and config.logging.enabled:
        log_dir = os.path.dirname(config.logging.file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        logging.basicConfig(
            level=getattr(logging, config.logging.level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(config.logging.file),
                logging.StreamHandler(sys.stderr),
            ],
        )
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("vLLM MCP Delegator Starting (Enhanced Version)")
        logger.info(f"Log Level: {config.logging.level}")
        logger.info(f"Log File: {config.logging.file}")
        logger.info("=" * 50)
    else:
        logging.basicConfig(
            level=logging.ERROR,
            format="%(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )

    return logging.getLogger(__name__)


def log_info(msg, config=None):
    """Log info message if logging is enabled"""
    if config and config.logging and config.logging.enabled:
        logging.getLogger(__name__).info(msg)


def log_debug(msg, config=None):
    """Log debug message if logging is enabled"""
    if config and config.logging and config.logging.enabled:
        logging.getLogger(__name__).debug(msg)


def log_error(msg, exc_info=False):
    """Log error message (always enabled)"""
    logging.getLogger(__name__).error(msg, exc_info=exc_info)
