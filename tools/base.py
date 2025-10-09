"""
Base functionality for tool implementations
"""

import time
from typing import List

from mcp.types import TextContent, Tool

from core.metrics import metrics_collector
from utils.errors import create_error_response
from utils.logging import log_debug, log_error, log_info


class BaseTool:
    """Base class for tool implementations"""

    def __init__(self, config=None):
        self.config = config

    async def execute(self, name: str, arguments: dict) -> List[TextContent]:
        """Execute a tool with metrics tracking"""
        start_time = time.time()
        log_info(f"Executing tool: {name}")
        log_debug(f"Arguments: {arguments}")

        try:
            result = await self._execute_impl(name, arguments)
            metrics_collector.record_execution(name, start_time, True)
            return result
        except Exception as e:
            log_error(f"Error in {name}: {e}", exc_info=True)
            metrics_collector.record_execution(
                name, start_time, False, error_type=type(e).__name__
            )
            return create_error_response(name, str(e))

    async def _execute_impl(self, name: str, arguments: dict) -> List[TextContent]:
        """Override this method in subclasses"""
        raise NotImplementedError("Subclasses must implement _execute_impl")


def create_health_check_tool() -> Tool:
    """Create health check tool definition"""
    return Tool(
        name="health_check",
        description="Check system health, vLLM connectivity, and service metrics",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )


def create_simple_code_tool() -> Tool:
    """Create simple code generation tool definition"""
    return Tool(
        name="generate_simple_code",
        description="Delegate simple, straightforward code generation to local Qwen2.5-Coder LLM. Use for: boilerplate code, basic CRUD functions, simple utility functions, standard implementations, repetitive code patterns. NOT for: complex algorithms, architectural decisions, code requiring deep context.",
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Clear, specific prompt for code generation",
                },
                "language": {
                    "type": "string",
                    "description": "Programming language (e.g., python, javascript, rust)",
                    "default": "python",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens to generate",
                    "default": 1000,
                },
            },
            "required": ["prompt"],
        },
    )
