#!/usr/bin/env python3
"""
Create security and utils module files
"""

from pathlib import Path


def create_security_utils_files():
    """Create security and utilities module files"""

    base_dir = Path(".")

    # Security module
    security_dir = base_dir / "security"
    security_dir.mkdir(parents=True, exist_ok=True)

    # security/utils.py
    security_content = '''"""
Security utilities for path validation and command checking
"""

import os
import shutil
import time
from pathlib import Path
from typing import List


def safe_path(base_path: str, target_path: str, allowed_paths: List[str] = None) -> str:
    """Validate that target_path is within base_path to prevent directory traversal"""
    base = Path(base_path).resolve()
    target = (base / target_path).resolve()

    if not target.is_relative_to(base):
        raise ValueError(f"Path {target_path} is outside allowed directory")

    # Additional check against configured allowed paths
    if allowed_paths:
        for allowed_path in allowed_paths:
            allowed = Path(allowed_path).resolve()
            if target.is_relative_to(allowed):
                return str(target)

    raise ValueError(f"Path {target_path} is not in allowed directories")


def validate_command(cmd_parts: List[str], allowed_commands: dict = None) -> bool:
    """Validate command against allowed commands"""
    if not cmd_parts:
        return False

    if not allowed_commands:
        return False

    base_cmd = cmd_parts[0]
    if base_cmd not in allowed_commands:
        return False

    # Check if subcommand is allowed
    allowed_subcmds = allowed_commands[base_cmd]
    if len(cmd_parts) > 1 and cmd_parts[1] not in allowed_subcmds:
        return False

    return True


def validate_file_size(file_path: str, max_size: int = 1024 * 1024) -> bool:
    """Check if file size is within limits"""
    try:
        size = os.path.getsize(file_path)
        return size <= max_size
    except OSError:
        return False


def create_backup(file_path: str, auto_backup: bool = True) -> str:
    """Create backup of file before modification"""
    if auto_backup and os.path.exists(file_path):
        backup_path = f"{file_path}.backup.{int(time.time())}"
        shutil.copy2(file_path, backup_path)
        return backup_path
    return None
'''

    # Utils module
    utils_dir = base_dir / "utils"
    utils_dir.mkdir(parents=True, exist_ok=True)

    # utils/logging.py
    logging_content = '''"""
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
'''

    # utils/errors.py
    errors_content = '''"""
Error handling utilities
"""

import json
from datetime import datetime
from mcp.types import TextContent


class ToolError(Exception):
    """Custom exception for tool errors"""

    def __init__(self, tool_name: str, error: str, context: dict = None):
        self.tool_name = tool_name
        self.error = error
        self.context = context or {}
        super().__init__(f"{tool_name}: {error}")


def create_error_response(tool_name: str, error: str, context: dict = None):
    """Create standardized error response"""
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "ok": False,
                    "tool": tool_name,
                    "error": error,
                    "context": context,
                    "timestamp": datetime.now().isoformat(),
                },
                indent=2,
            ),
        )
    ]


def create_success_response(data: dict):
    """Create standardized success response"""
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "ok": True,
                    "timestamp": datetime.now().isoformat(),
                    **data,
                },
                indent=2,
            ),
        )
    ]
'''

    # Write files
    security_files = {
        "utils.py": security_content,
    }

    utils_files = {
        "logging.py": logging_content,
        "errors.py": errors_content,
    }

    for filename, content in security_files.items():
        file_path = security_dir / filename
        file_path.write_text(content)
        print(f"Created: {file_path}")

    for filename, content in utils_files.items():
        file_path = utils_dir / filename
        file_path.write_text(content)
        print(f"Created: {file_path}")

    print("Security and utils files created successfully!")


if __name__ == "__main__":
    create_security_utils_files()
