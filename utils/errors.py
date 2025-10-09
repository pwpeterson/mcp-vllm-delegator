"""
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
