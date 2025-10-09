#!/usr/bin/env python3
"""
Create core module files
"""

from pathlib import Path


def create_core_files():
    """Create all core module files"""

    base_dir = Path(".")
    core_dir = base_dir / "core"

    # Ensure directory exists
    core_dir.mkdir(parents=True, exist_ok=True)

    # core/client.py
    client_content = '''"""
vLLM client management and API interaction
"""

import asyncio
import httpx
from typing import Optional, Callable, Any

from config.models import get_model_config
from core.cache import response_cache
from core.validation import validate_llm_response
from utils.logging import log_debug, log_error


class VLLMClient:
    """Singleton vLLM client with connection management"""
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self, timeout: int = 180):
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


# Global client instance
vllm_client = VLLMClient()


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Any:
    """Execute function with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return await func()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2**attempt), max_delay)
            log_debug(f"Retry attempt {attempt + 1}, waiting {delay}s")
            await asyncio.sleep(delay)


async def call_vllm_api(
    prompt: str,
    task_type: str = "code_generation",
    language: str = None,
    config = None
) -> str:
    """Enhanced LLM API call with retry logic and caching"""

    # Check cache first
    cached_response = response_cache.get(task_type, prompt=prompt)
    if cached_response:
        log_debug(f"Cache hit for {task_type}")
        return cached_response

    model_config = get_model_config(task_type, config.vllm if config else None)

    async def make_request():
        client = await vllm_client.get_client(
            timeout=config.vllm.timeout if config and config.vllm else 180
        )
        api_url = config.vllm.api_url if config and config.vllm else "http://localhost:8002/v1/chat/completions"
        response = await client.post(
            api_url,
            json={"messages": [{"role": "user", "content": prompt}], **model_config},
        )
        response.raise_for_status()
        return response.json()

    try:
        result = await retry_with_backoff(
            make_request,
            max_retries=config.vllm.max_retries if config and config.vllm else 3,
            base_delay=config.vllm.base_delay if config and config.vllm else 1.0,
            max_delay=config.vllm.max_delay if config and config.vllm else 60.0,
        )
        content = result["choices"][0]["message"]["content"]

        # Validate response
        validate_llm_response(content, language=language, config=config)

        # Cache the response
        response_cache.set(task_type, content, prompt=prompt)

        return content
    except Exception as e:
        log_error(f"vLLM API call failed: {e}")
        raise
'''

    # core/cache.py
    cache_content = '''"""
Response caching system for LLM API calls
"""

import hashlib
import json
from typing import Optional


class ResponseCache:
    """Simple in-memory cache for LLM responses"""

    def __init__(self):
        self.cache = {}
        self.max_size = 100

    def _generate_key(self, tool_name: str, **kwargs) -> str:
        """Generate cache key from tool name and arguments"""
        key_data = f"{tool_name}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, tool_name: str, **kwargs) -> Optional[str]:
        """Get cached response if available"""
        key = self._generate_key(tool_name, **kwargs)
        return self.cache.get(key)

    def set(self, tool_name: str, response: str, **kwargs):
        """Cache a response"""
        key = self._generate_key(tool_name, **kwargs)
        self.cache[key] = response

        # Simple LRU: remove oldest entries
        if len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

    def clear(self):
        """Clear all cached responses"""
        self.cache.clear()


# Global cache instance
response_cache = ResponseCache()
'''

    # core/metrics.py
    metrics_content = '''"""
Metrics collection and monitoring
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ToolMetrics:
    tool_name: str
    execution_time: float
    success: bool
    error_type: Optional[str] = None
    tokens_used: int = 0
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class MetricsCollector:
    """Collect and analyze tool execution metrics"""

    def __init__(self):
        self.metrics: List[ToolMetrics] = []
        self.max_metrics = 1000  # Keep last 1000 metrics

    def record_execution(
        self, tool_name: str, start_time: float, success: bool, **kwargs
    ):
        """Record a tool execution"""
        metric = ToolMetrics(
            tool_name=tool_name,
            execution_time=time.time() - start_time,
            success=success,
            **kwargs,
        )
        self.metrics.append(metric)

        # Keep only recent metrics
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics :]

    def get_stats(self) -> Dict:
        """Get aggregated statistics"""
        if not self.metrics:
            return {"total_calls": 0}

        total_calls = len(self.metrics)
        successful_calls = sum(1 for m in self.metrics if m.success)
        avg_execution_time = sum(m.execution_time for m in self.metrics) / total_calls

        tool_stats = {}
        for metric in self.metrics:
            if metric.tool_name not in tool_stats:
                tool_stats[metric.tool_name] = {
                    "calls": 0,
                    "successes": 0,
                    "avg_time": 0,
                }
            tool_stats[metric.tool_name]["calls"] += 1
            if metric.success:
                tool_stats[metric.tool_name]["successes"] += 1

        return {
            "total_calls": total_calls,
            "success_rate": successful_calls / total_calls if total_calls > 0 else 0,
            "avg_execution_time": avg_execution_time,
            "tool_stats": tool_stats,
            "recent_errors": [
                m.error_type
                for m in self.metrics[-10:]
                if not m.success and m.error_type
            ],
        }

    def clear_metrics(self):
        """Clear all collected metrics"""
        self.metrics.clear()


# Global metrics collector
metrics_collector = MetricsCollector()
'''

    # core/validation.py
    validation_content = '''"""
Validation utilities for LLM responses and code
"""

from config.models import detect_language_from_code


def validate_llm_code_response(code: str, language: str) -> bool:
    """Enhanced validation for code responses"""
    if not code.strip():
        raise ValueError("LLM returned empty code")

    # Language-specific syntax validation
    if language == "python":
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax: {e}")
    elif language == "javascript":
        # Basic JS validation - check for common syntax errors
        if code.count('{') != code.count('}'):
            raise ValueError("Mismatched braces in JavaScript code")
        if code.count('(') != code.count(')'):
            raise ValueError("Mismatched parentheses in JavaScript code")
    elif language == "typescript":
        # Similar to JavaScript for basic checks
        if code.count('{') != code.count('}'):
            raise ValueError("Mismatched braces in TypeScript code")
        if code.count('(') != code.count(')'):
            raise ValueError("Mismatched parentheses in TypeScript code")
    # Add more languages as needed

    return True


def validate_llm_response(content: str, original_content: str = "", language: str = None, config=None) -> bool:
    """Validate LLM response for safety"""
    max_length = config.security.max_response_length if config and config.security else 50000
    if len(content) > max_length:
        raise ValueError("LLM response too large")

    if original_content and len(content) < len(original_content) * 0.3:
        raise ValueError("LLM response suspiciously short")

    # Add code validation for supported languages
    if language:
        validate_llm_code_response(content, language)

    return True
'''

    # Write files
    files = {
        "client.py": client_content,
        "cache.py": cache_content,
        "metrics.py": metrics_content,
        "validation.py": validation_content,
    }

    for filename, content in files.items():
        file_path = core_dir / filename
        file_path.write_text(content)
        print(f"Created: {file_path}")

    print("Core files created successfully!")


if __name__ == "__main__":
    create_core_files()
