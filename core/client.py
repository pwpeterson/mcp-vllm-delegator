"""
vLLM client management and API interaction
"""

import asyncio
import time
from typing import Any, Callable

import httpx

from config.models import get_model_config
from core.cache import response_cache
from core.validation import validate_llm_response
from utils.logging import log_error, log_system_event, log_vllm_request


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
                log_system_event(
                    "error", f"vLLM retry failed after {max_retries} attempts", str(e)
                )
                raise
            delay = min(base_delay * (2**attempt), max_delay)
            log_system_event(
                "warning",
                f"vLLM retry attempt {attempt + 1}",
                f"waiting {delay}s - {type(e).__name__}",
            )
            await asyncio.sleep(delay)


async def call_vllm_api(
    prompt: str,
    task_type: str = "code_generation",
    language: str | None = None,
    config=None,
) -> str:
    """Enhanced LLM API call with retry logic and caching"""
    start_time = time.time()
    model_name = config.vllm.model if config and config.vllm else "unknown"

    # Check cache first
    cached_response = response_cache.get(task_type, prompt=prompt)
    if cached_response:
        log_system_event(
            "performance",
            f"Cache hit for {task_type}",
            f"Saved API call - {len(cached_response)} chars",
        )
        return cached_response

    log_system_event(
        "performance",
        "vLLM API call starting",
        f"Task: {task_type}, Prompt: {len(prompt)} chars",
    )
    model_config = get_model_config(task_type, config.vllm if config else None)

    async def make_request():
        client = await vllm_client.get_client(
            timeout=config.vllm.timeout if config and config.vllm else 180
        )
        api_url = (
            config.vllm.api_url
            if config and config.vllm
            else "http://localhost:8002/v1/chat/completions"
        )
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
        duration = time.time() - start_time

        # Log successful API call
        log_vllm_request(model_name, len(prompt), len(content), duration, success=True)
        log_system_event(
            "performance",
            "vLLM API call completed",
            f"Task: {task_type}, Duration: {duration:.3f}s",
        )

        # Validate response
        validate_llm_response(content, language=language, config=config)

        # Cache the response
        response_cache.set(task_type, content, prompt=prompt)
        log_system_event(
            "performance",
            "Response cached",
            f"Task: {task_type}, Size: {len(content)} chars",
        )

        return content
    except Exception as e:
        duration = time.time() - start_time
        log_vllm_request(model_name, len(prompt), duration=duration, success=False)
        log_system_event(
            "error",
            "vLLM API call failed",
            f"Task: {task_type}, Duration: {duration:.3f}s, Error: {str(e)}",
        )
        log_error(f"vLLM API call failed: {e}")
        raise
