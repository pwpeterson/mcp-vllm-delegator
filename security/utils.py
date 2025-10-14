"""
Security utilities for path validation and command checking
"""

import os
import shutil
import time
from pathlib import Path
from typing import List


def safe_path(
    base_path: str, target_path: str, allowed_paths: List[str] | None = None
) -> str:
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


def validate_command(
    cmd_parts: List[str], allowed_commands: dict | None = None
) -> bool:
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


def create_backup(file_path: str, auto_backup: bool = True) -> str | None:
    """Create backup of file before modification"""
    if auto_backup and os.path.exists(file_path):
        backup_path = f"{file_path}.backup.{int(time.time())}"
        shutil.copy2(file_path, backup_path)
        return backup_path
    return None
