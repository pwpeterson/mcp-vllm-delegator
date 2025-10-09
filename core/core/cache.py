"""
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
