# mcp_vllm_delegator.py
import asyncio
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import yaml
from mcp.server import Server
from mcp.types import TextContent, Tool


# ========== CONFIGURATION MANAGEMENT ==========
@dataclass
class VLLMConfig:
    api_url: str = "http://localhost:8002/v1/chat/completions"
    model: str = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
    timeout: int = 180
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0


@dataclass
class SecurityConfig:
    allowed_paths: List[str] = None
    max_file_size: int = 1024 * 1024  # 1MB
    max_response_length: int = 50000
    allowed_commands: Dict[str, List[str]] = None

    def __post_init__(self):
        if self.allowed_paths is None:
            self.allowed_paths = [os.getcwd()]
        if self.allowed_commands is None:
            self.allowed_commands = {
                "npm": ["install", "test", "run", "build", "start"],
                "pip": ["install", "list", "show", "freeze"],
                "cargo": ["build", "test", "check", "run"],
                "git": ["status", "add", "commit", "push", "pull", "log", "diff"],
                "pre-commit": ["run", "install", "autoupdate"],
                "python": ["-m", "-c"],
                "make": ["build", "test", "clean", "install"],
            }


@dataclass
class LoggingConfig:
    enabled: bool = True
    level: str = "INFO"
    file: str = "/tmp/vllm_mcp_delegator.log"


@dataclass
class FeaturesConfig:
    caching: bool = True
    metrics: bool = True
    auto_backup: bool = True
    batch_operations: bool = True


@dataclass
class Config:
    vllm: VLLMConfig = None
    security: SecurityConfig = None
    logging: LoggingConfig = None
    features: FeaturesConfig = None

    def __post_init__(self):
        if self.vllm is None:
            self.vllm = VLLMConfig()
        if self.security is None:
            self.security = SecurityConfig()
        if self.logging is None:
            self.logging = LoggingConfig()
        if self.features is None:
            self.features = FeaturesConfig()


def load_config() -> Config:
    """Load configuration from file or environment variables"""
    config_file = os.getenv("CONFIG_FILE", "config.yaml")

    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config_data = yaml.safe_load(f)
            return Config(
                **{
                    k: type(getattr(Config, k)).__call__(**v)
                    if isinstance(v, dict)
                    else v
                    for k, v in config_data.items()
                }
            )
        except Exception as e:
            print(f"Failed to load config file: {e}")

    # Fallback to environment variables
    return Config(
        vllm=VLLMConfig(
            api_url=os.getenv(
                "VLLM_API_URL", "http://localhost:8002/v1/chat/completions"
            ),
            model=os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"),
        ),
        logging=LoggingConfig(
            enabled=os.getenv("LOGGING_ON", "true").lower()
            in ("true", "1", "yes", "on"),
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            file=os.getenv("LOG_FILE", "/tmp/vllm_mcp_delegator.log"),
        ),
    )


# Load global configuration
CONFIG = load_config()

# ========== LOGGING SETUP ==========
if CONFIG.logging.enabled:
    log_dir = os.path.dirname(CONFIG.logging.file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, CONFIG.logging.level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(CONFIG.logging.file),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("vLLM MCP Delegator Starting (Enhanced Version)")
    logger.info(f"Log Level: {CONFIG.logging.level}")
    logger.info(f"Log File: {CONFIG.logging.file}")
    logger.info("=" * 50)
else:
    logging.basicConfig(
        level=logging.ERROR,
        format="%(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logger = logging.getLogger(__name__)


def log_info(msg):
    if CONFIG.logging.enabled:
        logger.info(msg)


def log_debug(msg):
    if CONFIG.logging.enabled:
        logger.debug(msg)


def log_error(msg, exc_info=False):
    logger.error(msg, exc_info=exc_info)


# ========== METRICS AND MONITORING ==========
@dataclass
class ToolMetrics:
    tool_name: str
    execution_time: float
    success: bool
    error_type: Optional[str] = None
    tokens_used: int = 0
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class MetricsCollector:
    def __init__(self):
        self.metrics: List[ToolMetrics] = []
        self.max_metrics = 1000  # Keep last 1000 metrics

    def record_execution(
        self, tool_name: str, start_time: float, success: bool, **kwargs
    ):
        if CONFIG.features.metrics:
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


metrics_collector = MetricsCollector()


# ========== SECURITY UTILITIES ==========
def safe_path(base_path: str, target_path: str) -> str:
    """Validate that target_path is within base_path to prevent directory traversal"""
    base = Path(base_path).resolve()
    target = (base / target_path).resolve()

    if not target.is_relative_to(base):
        raise ValueError(f"Path {target_path} is outside allowed directory")

    # Additional check against configured allowed paths
    for allowed_path in CONFIG.security.allowed_paths:
        allowed = Path(allowed_path).resolve()
        if target.is_relative_to(allowed):
            return str(target)

    raise ValueError(f"Path {target_path} is not in allowed directories")


def validate_command(cmd_parts: List[str]) -> bool:
    """Validate command against allowed commands"""
    if not cmd_parts:
        return False

    base_cmd = cmd_parts[0]
    if base_cmd not in CONFIG.security.allowed_commands:
        return False

    # Check if subcommand is allowed
    allowed_subcmds = CONFIG.security.allowed_commands[base_cmd]
    if len(cmd_parts) > 1 and cmd_parts[1] not in allowed_subcmds:
        return False

    return True


def validate_file_size(file_path: str) -> bool:
    """Check if file size is within limits"""
    try:
        size = os.path.getsize(file_path)
        return size <= CONFIG.security.max_file_size
    except OSError:
        return False


def validate_llm_response(content: str, original_content: str = "") -> bool:
    """Validate LLM response for safety"""
    if len(content) > CONFIG.security.max_response_length:
        raise ValueError("LLM response too large")

    if original_content and len(content) < len(original_content) * 0.3:
        raise ValueError("LLM response suspiciously short")

    return True


def create_backup(file_path: str) -> str:
    """Create backup of file before modification"""
    if CONFIG.features.auto_backup and os.path.exists(file_path):
        backup_path = f"{file_path}.backup.{int(time.time())}"
        shutil.copy2(file_path, backup_path)
        return backup_path
    return None


# ========== ERROR HANDLING ==========
class ToolError(Exception):
    def __init__(self, tool_name: str, error: str, context: dict = None):
        self.tool_name = tool_name
        self.error = error
        self.context = context or {}
        super().__init__(f"{tool_name}: {error}")


def create_error_response(tool_name: str, error: str, context: dict = None):
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


async def retry_with_backoff(
    func: Callable,
    max_retries: int = None,
    base_delay: float = None,
    max_delay: float = None,
) -> Any:
    """Execute function with exponential backoff retry"""
    max_retries = max_retries or CONFIG.vllm.max_retries
    base_delay = base_delay or CONFIG.vllm.base_delay
    max_delay = max_delay or CONFIG.vllm.max_delay

    for attempt in range(max_retries):
        try:
            return await func()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2**attempt), max_delay)
            log_debug(f"Retry attempt {attempt + 1}, waiting {delay}s")
            await asyncio.sleep(delay)


# ========== VLLM CLIENT MANAGEMENT ==========
class VLLMClient:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=CONFIG.vllm.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


vllm_client = VLLMClient()


# ========== CACHING SYSTEM ==========
class ResponseCache:
    def __init__(self):
        self.cache = {}
        self.max_size = 100

    def _generate_key(self, tool_name: str, **kwargs) -> str:
        """Generate cache key from tool name and arguments"""
        key_data = f"{tool_name}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, tool_name: str, **kwargs) -> Optional[str]:
        if not CONFIG.features.caching:
            return None

        key = self._generate_key(tool_name, **kwargs)
        return self.cache.get(key)

    def set(self, tool_name: str, response: str, **kwargs):
        if not CONFIG.features.caching:
            return

        key = self._generate_key(tool_name, **kwargs)
        self.cache[key] = response

        # Simple LRU: remove oldest entries
        if len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]


response_cache = ResponseCache()

# ========== MODEL CONFIGURATIONS ==========
MODEL_CONFIGS = {
    "code_generation": {"temperature": 0.2, "max_tokens": 2000},
    "documentation": {"temperature": 0.3, "max_tokens": 1500},
    "analysis": {"temperature": 0.1, "max_tokens": 1000},
    "git_commit": {"temperature": 0.3, "max_tokens": 200},
    "explanation": {"temperature": 0.3, "max_tokens": 800},
}


def get_model_config(task_type: str) -> dict:
    """Get model configuration for specific task type"""
    config = MODEL_CONFIGS.get(task_type, MODEL_CONFIGS["code_generation"])
    return {"model": CONFIG.vllm.model, **config}


# ========== ENHANCED LLM INTERACTION ==========
async def call_vllm_api(prompt: str, task_type: str = "code_generation") -> str:
    """Enhanced LLM API call with retry logic and caching"""

    # Check cache first
    cached_response = response_cache.get(task_type, prompt=prompt)
    if cached_response:
        log_debug(f"Cache hit for {task_type}")
        return cached_response

    config = get_model_config(task_type)

    async def make_request():
        client = await vllm_client.get_client()
        response = await client.post(
            CONFIG.vllm.api_url,
            json={"messages": [{"role": "user", "content": prompt}], **config},
        )
        response.raise_for_status()
        return response.json()

    try:
        result = await retry_with_backoff(make_request)
        content = result["choices"][0]["message"]["content"]

        # Validate response
        validate_llm_response(content)

        # Cache the response
        response_cache.set(task_type, content, prompt=prompt)

        return content
    except Exception as e:
        log_error(f"vLLM API call failed: {e}")
        raise


# ========== LANGUAGE DETECTION ==========
LANGUAGE_CONFIGS = {
    "python": {
        "file_extensions": [".py"],
        "test_framework": "pytest",
        "linter": "flake8",
        "formatter": "black",
    },
    "javascript": {
        "file_extensions": [".js", ".ts", ".jsx", ".tsx"],
        "test_framework": "jest",
        "linter": "eslint",
        "formatter": "prettier",
    },
    "rust": {
        "file_extensions": [".rs"],
        "test_framework": "cargo-test",
        "linter": "clippy",
        "formatter": "rustfmt",
    },
    "go": {
        "file_extensions": [".go"],
        "test_framework": "go test",
        "linter": "golint",
        "formatter": "gofmt",
    },
}


def detect_project_language(working_dir: str) -> str:
    """Auto-detect primary project language"""
    file_counts = {}

    for lang, config in LANGUAGE_CONFIGS.items():
        count = 0
        for ext in config["file_extensions"]:
            pattern = f"**/*{ext}"
            count += len(list(Path(working_dir).glob(pattern)))
        file_counts[lang] = count

    # Return language with most files, or python as default
    return (
        max(file_counts, key=file_counts.get) if any(file_counts.values()) else "python"
    )


# ========== SERVER INITIALIZATION ==========
server = Server("vllm-delegator-enhanced")

log_info(f"vLLM API URL: {CONFIG.vllm.api_url}")
log_info(f"vLLM Model: {CONFIG.vllm.model}")
log_info(f"Security: Allowed paths: {CONFIG.security.allowed_paths}")
log_info(
    f"Features: Caching={CONFIG.features.caching}, Metrics={CONFIG.features.metrics}"
)


# ========== TOOL DEFINITIONS ==========
@server.list_tools()
async def list_tools() -> list[Tool]:
    log_info("list_tools() called")
    tools = [
        Tool(
            name="health_check",
            description="Check system health, vLLM connectivity, and service metrics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
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
        ),
        Tool(
            name="complete_code",
            description="Complete or extend existing code using local LLM. Good for: filling in function bodies, completing class methods, adding docstrings, implementing obvious next steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_context": {
                        "type": "string",
                        "description": "Existing code that needs completion",
                    },
                    "instruction": {
                        "type": "string",
                        "description": "What to complete or add",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate",
                        "default": 800,
                    },
                },
                "required": ["code_context", "instruction"],
            },
        ),
        Tool(
            name="explain_code",
            description="Get quick code explanations from local LLM for simple code snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to explain"},
                    "detail_level": {
                        "type": "string",
                        "enum": ["brief", "detailed"],
                        "default": "brief",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="analyze_codebase",
            description="Analyze codebase structure and provide insights about architecture, patterns, and potential improvements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to analyze",
                        "default": ".",
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["structure", "quality", "patterns", "dependencies"],
                        "default": "structure",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="detect_code_smells",
            description="Use LLM to identify potential code quality issues and technical debt.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to analyze"},
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="git_smart_commit",
            description="Analyze changes and generate appropriate commit message automatically, then commit and push.",
            inputSchema={
                "type": "object",
                "properties": {
                    "auto_push": {
                        "type": "boolean",
                        "description": "Automatically push after successful commit",
                        "default": True,
                    },
                    "commit_type": {
                        "type": "string",
                        "enum": [
                            "feat",
                            "fix",
                            "docs",
                            "style",
                            "refactor",
                            "test",
                            "chore",
                            "auto",
                        ],
                        "default": "auto",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_docstrings",
            description="Generate docstrings/comments for code using local LLM. Use for: function/class documentation, inline comments for simple logic. Supports multiple documentation styles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code that needs documentation",
                    },
                    "style": {
                        "type": "string",
                        "enum": ["google", "numpy", "sphinx", "jsdoc", "rustdoc"],
                        "default": "google",
                        "description": "Documentation style to use",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="generate_tests",
            description="Generate basic unit tests using local LLM. Use for: simple function tests, basic edge cases, happy path tests. NOT for: integration tests, complex mocking scenarios.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to generate tests for",
                    },
                    "test_framework": {
                        "type": "string",
                        "enum": [
                            "pytest",
                            "unittest",
                            "jest",
                            "mocha",
                            "vitest",
                            "cargo-test",
                        ],
                        "default": "pytest",
                        "description": "Testing framework to use",
                    },
                    "coverage_level": {
                        "type": "string",
                        "enum": ["basic", "standard", "comprehensive"],
                        "default": "standard",
                        "description": "basic=happy path, standard=+edge cases, comprehensive=+error cases",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="refactor_simple_code",
            description="Refactor simple code patterns using local LLM. Use for: variable renaming, extract method, simplify conditionals, remove duplication in straightforward code. NOT for: complex architectural refactoring, cross-file changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to refactor"},
                    "refactor_type": {
                        "type": "string",
                        "description": "Type of refactoring (e.g., 'extract method', 'rename variables', 'simplify conditionals', 'remove duplication')",
                    },
                    "additional_context": {
                        "type": "string",
                        "description": "Additional context or constraints for refactoring",
                        "default": "",
                    },
                },
                "required": ["code", "refactor_type"],
            },
        ),
        Tool(
            name="fix_simple_bugs",
            description="Fix straightforward bugs using local LLM. Use for: syntax errors, simple logic errors, obvious type mismatches, missing imports for standard libraries. NOT for: race conditions, memory leaks, complex logic errors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code containing the bug",
                    },
                    "error_message": {
                        "type": "string",
                        "description": "Error message or bug description",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about the bug",
                        "default": "",
                    },
                },
                "required": ["code", "error_message"],
            },
        ),
        Tool(
            name="convert_code_format",
            description="Convert between code formats/styles using local LLM. Use for: camelCase to snake_case, JSON to YAML, SQL to ORM, callback to async/await (simple cases).",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to convert"},
                    "from_format": {
                        "type": "string",
                        "description": "Current format (e.g., 'camelCase', 'json', 'callbacks', 'sql')",
                    },
                    "to_format": {
                        "type": "string",
                        "description": "Target format (e.g., 'snake_case', 'yaml', 'async/await', 'orm')",
                    },
                },
                "required": ["code", "from_format", "to_format"],
            },
        ),
        Tool(
            name="generate_boilerplate_file",
            description="Generate complete boilerplate files using local LLM. Use for: REST API routes, database models, config files, Dockerfiles, GitHub Actions workflows, basic CLI scripts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_type": {
                        "type": "string",
                        "description": "Type of file to generate (e.g., 'rest_api_route', 'database_model', 'dockerfile', 'github_action', 'cli_script')",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language or config format",
                        "default": "python",
                    },
                    "options": {
                        "type": "object",
                        "description": "Additional options as key-value pairs (e.g., framework, database_type, authentication)",
                        "default": {},
                    },
                },
                "required": ["file_type", "language"],
            },
        ),
        Tool(
            name="improve_code_style",
            description="Improve code style/readability using local LLM. Use for: consistent naming, line length, import ordering, simple readability improvements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to improve"},
                    "style_guide": {
                        "type": "string",
                        "enum": [
                            "pep8",
                            "black",
                            "airbnb",
                            "google",
                            "standard",
                            "prettier",
                        ],
                        "default": "pep8",
                        "description": "Style guide to follow",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="generate_schema",
            description="Generate data schemas/models using local LLM. Schema types: pydantic, sqlalchemy, json_schema, graphql, typescript_interface, protobuf. Use for: straightforward data models with standard field types.",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of the data structure to generate",
                    },
                    "schema_type": {
                        "type": "string",
                        "enum": [
                            "pydantic",
                            "sqlalchemy",
                            "json_schema",
                            "graphql",
                            "typescript_interface",
                            "protobuf",
                        ],
                        "description": "Type of schema to generate",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["description", "schema_type"],
            },
        ),
        Tool(
            name="generate_git_commit_message",
            description="Generate conventional commit messages using local LLM. Use for: creating clear, descriptive commit messages following conventional commit format.",
            inputSchema={
                "type": "object",
                "properties": {
                    "changes_summary": {
                        "type": "string",
                        "description": "Summary of changes made (can be git diff output or description)",
                    },
                    "commit_type": {
                        "type": "string",
                        "enum": [
                            "feat",
                            "fix",
                            "docs",
                            "style",
                            "refactor",
                            "test",
                            "chore",
                            "auto",
                        ],
                        "default": "auto",
                        "description": "Type of commit (auto = let LLM decide)",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Optional scope of the change (e.g., 'api', 'ui', 'auth')",
                        "default": "",
                    },
                },
                "required": ["changes_summary"],
            },
        ),
        Tool(
            name="generate_gitignore",
            description="Generate .gitignore files using local LLM. Use for: creating comprehensive .gitignore files for specific languages/frameworks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Primary programming language (e.g., python, javascript, rust, go)",
                    },
                    "frameworks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional frameworks/tools (e.g., ['react', 'docker', 'vscode'])",
                        "default": [],
                    },
                    "custom_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Custom patterns to include",
                        "default": [],
                    },
                },
                "required": ["language"],
            },
        ),
        Tool(
            name="generate_github_workflow",
            description="Generate GitHub Actions workflow files using local LLM. Use for: CI/CD pipelines, automated testing, deployment workflows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_type": {
                        "type": "string",
                        "enum": [
                            "ci",
                            "cd",
                            "test",
                            "release",
                            "lint",
                            "security",
                            "custom",
                        ],
                        "description": "Type of workflow to generate",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "triggers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Workflow triggers (e.g., ['push', 'pull_request', 'schedule'])",
                        "default": ["push", "pull_request"],
                    },
                    "custom_requirements": {
                        "type": "string",
                        "description": "Additional requirements or steps",
                        "default": "",
                    },
                },
                "required": ["workflow_type"],
            },
        ),
        Tool(
            name="generate_pr_description",
            description="Generate pull request descriptions using local LLM. Use for: creating comprehensive PR descriptions with context and changes summary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "changes_summary": {
                        "type": "string",
                        "description": "Summary of changes made (can be git diff output or description)",
                    },
                    "pr_type": {
                        "type": "string",
                        "enum": [
                            "feature",
                            "bugfix",
                            "hotfix",
                            "refactor",
                            "docs",
                            "chore",
                        ],
                        "description": "Type of pull request",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about why these changes were made",
                        "default": "",
                    },
                    "breaking_changes": {
                        "type": "boolean",
                        "description": "Whether this PR contains breaking changes",
                        "default": False,
                    },
                },
                "required": ["changes_summary", "pr_type"],
            },
        ),
        Tool(
            name="git_status",
            description="Execute git status command. Shows working tree status including modified, added, deleted, and untracked files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "porcelain": {
                        "type": "boolean",
                        "description": "Use porcelain format for machine-readable output",
                        "default": True,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="git_add",
            description="Execute git add command to stage files for commit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to add (use ['.'] for all files)",
                    }
                },
                "required": ["files"],
            },
        ),
        Tool(
            name="git_commit",
            description="Execute git commit command with message. Automatically pushes to origin if successful.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "auto_push": {
                        "type": "boolean",
                        "description": "Automatically push after successful commit",
                        "default": True,
                    },
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="git_diff",
            description="Execute git diff command to show changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "Show staged changes (--cached)",
                        "default": False,
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific files to diff (optional)",
                        "default": [],
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="git_log",
            description="Execute git log command to show commit history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of commits to show",
                        "default": 10,
                    },
                    "oneline": {
                        "type": "boolean",
                        "description": "Show one line per commit",
                        "default": True,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="create_config_file",
            description="Generate and create common configuration files using local LLM. Use for: .env, package.json, requirements.txt, Dockerfile, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_type": {
                        "type": "string",
                        "enum": [
                            "env",
                            "package_json",
                            "requirements_txt",
                            "dockerfile",
                            "makefile",
                            "gitignore",
                            "readme",
                            "contributing",
                            "license",
                            "custom",
                        ],
                        "description": "Type of config file to generate",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path where to create the file",
                    },
                    "options": {
                        "type": "object",
                        "description": "Configuration options (e.g., project_name, language, dependencies)",
                        "default": {},
                    },
                    "custom_prompt": {
                        "type": "string",
                        "description": "Custom prompt for file generation (used with 'custom' file_type)",
                        "default": "",
                    },
                },
                "required": ["file_type", "path"],
            },
        ),
        Tool(
            name="create_directory_structure",
            description="Generate and create standard directory structures using local LLM. Use for: project scaffolding, standard layouts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "structure_type": {
                        "type": "string",
                        "enum": [
                            "python_project",
                            "node_project",
                            "rust_project",
                            "go_project",
                            "web_project",
                            "api_project",
                            "custom",
                        ],
                        "description": "Type of directory structure to create",
                    },
                    "base_path": {
                        "type": "string",
                        "description": "Base directory path",
                    },
                    "project_name": {"type": "string", "description": "Project name"},
                    "options": {
                        "type": "object",
                        "description": "Additional options (e.g., include_tests, include_docs)",
                        "default": {},
                    },
                },
                "required": ["structure_type", "base_path", "project_name"],
            },
        ),
        Tool(
            name="create_github_issue",
            description="Generate and create GitHub issues using local LLM. Use for: bug reports, feature requests, task issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "Repository in format 'owner/repo'",
                    },
                    "issue_type": {
                        "type": "string",
                        "enum": [
                            "bug",
                            "feature",
                            "enhancement",
                            "task",
                            "question",
                            "documentation",
                        ],
                        "description": "Type of issue",
                    },
                    "title": {"type": "string", "description": "Issue title"},
                    "description": {
                        "type": "string",
                        "description": "Issue description or context",
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to apply",
                        "default": [],
                    },
                },
                "required": ["repository", "issue_type", "title", "description"],
            },
        ),
        Tool(
            name="create_github_pr",
            description="Generate and create GitHub pull requests using local LLM. Use for: feature PRs, bug fixes, documentation updates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "Repository in format 'owner/repo'",
                    },
                    "head_branch": {"type": "string", "description": "Source branch"},
                    "base_branch": {
                        "type": "string",
                        "description": "Target branch",
                        "default": "main",
                    },
                    "title": {"type": "string", "description": "PR title"},
                    "changes_summary": {
                        "type": "string",
                        "description": "Summary of changes made",
                    },
                    "pr_type": {
                        "type": "string",
                        "enum": [
                            "feature",
                            "bugfix",
                            "hotfix",
                            "refactor",
                            "docs",
                            "chore",
                        ],
                        "description": "Type of pull request",
                    },
                },
                "required": [
                    "repository",
                    "head_branch",
                    "title",
                    "changes_summary",
                    "pr_type",
                ],
            },
        ),
        Tool(
            name="execute_dev_command",
            description="Execute common development commands using subprocess. Use for: package installation, build commands, test execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_type": {
                        "type": "string",
                        "enum": [
                            "npm_install",
                            "pip_install",
                            "cargo_build",
                            "go_mod_tidy",
                            "make",
                            "test",
                            "custom",
                        ],
                        "description": "Type of command to execute",
                    },
                    "arguments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command arguments",
                        "default": [],
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for command execution",
                        "default": ".",
                    },
                    "custom_command": {
                        "type": "string",
                        "description": "Custom command to execute (used with 'custom' command_type)",
                        "default": "",
                    },
                },
                "required": ["command_type"],
            },
        ),
        Tool(
            name="create_database_schema",
            description="Generate and execute SQLite database schema creation using local LLM. Use for: table creation, index creation, basic schema setup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_path": {
                        "type": "string",
                        "description": "Path to SQLite database file",
                    },
                    "schema_description": {
                        "type": "string",
                        "description": "Description of the schema to create",
                    },
                    "tables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                            },
                        },
                        "description": "Table specifications",
                        "default": [],
                    },
                },
                "required": ["database_path", "schema_description"],
            },
        ),
        Tool(
            name="generate_sql_queries",
            description="Generate common SQL queries using local LLM. Use for: CRUD operations, data analysis queries, reporting queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "select",
                            "insert",
                            "update",
                            "delete",
                            "create_table",
                            "create_index",
                            "analytics",
                        ],
                        "description": "Type of SQL query to generate",
                    },
                    "table_info": {
                        "type": "string",
                        "description": "Information about tables and columns involved",
                    },
                    "requirements": {
                        "type": "string",
                        "description": "Specific requirements for the query",
                    },
                    "execute": {
                        "type": "boolean",
                        "description": "Whether to execute the query (for safe operations only)",
                        "default": False,
                    },
                    "database_path": {
                        "type": "string",
                        "description": "Database path (required if execute=true)",
                        "default": "",
                    },
                },
                "required": ["query_type", "table_info", "requirements"],
            },
        ),
        Tool(
            name="validate",
            description="Run pre-commit validation on files using local subprocess. Use for: code style validation, linting, formatting checks. Runs 'pre-commit run --files <filename>' or 'pre-commit run --all-files'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to validate (empty array or omit for --all-files)",
                        "default": [],
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for pre-commit execution",
                        "default": ".",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="validate_correct",
            description="Run pre-commit validation and automatically correct issues using local LLM. First runs validation, then reads the output and corrects each file as specified in the pre-commit output.",
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to validate and correct (empty array or omit for --all-files)",
                        "default": [],
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for pre-commit execution",
                        "default": ".",
                    },
                    "max_corrections": {
                        "type": "integer",
                        "description": "Maximum number of files to auto-correct",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_code_review",
            description="Automated code review feedback using local LLM. Analyzes code changes and provides structured review comments for style, bugs, performance, and best practices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_diff": {
                        "type": "string",
                        "description": "Git diff or code changes to review",
                    },
                    "review_focus": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Focus areas for review",
                        "default": ["style", "bugs", "performance", "maintainability"],
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "severity_filter": {
                        "type": "string",
                        "enum": ["all", "medium_and_high", "high_only"],
                        "default": "all",
                        "description": "Filter review comments by severity",
                    },
                },
                "required": ["code_diff"],
            },
        ),
        Tool(
            name="suggest_refactoring_opportunities",
            description="Identify specific refactoring opportunities in code using local LLM. Provides ranked suggestions with before/after examples.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to analyze for refactoring",
                    },
                    "refactoring_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of refactoring to look for",
                        "default": [
                            "extract_method",
                            "reduce_complexity",
                            "remove_duplication",
                            "improve_naming",
                        ],
                    },
                    "complexity_threshold": {
                        "type": "integer",
                        "description": "Complexity threshold for suggestions",
                        "default": 10,
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="generate_performance_analysis",
            description="Analyze code for performance bottlenecks using local LLM. Identifies optimization opportunities and algorithmic improvements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to analyze for performance",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "performance_context": {
                        "type": "string",
                        "enum": [
                            "web_api",
                            "data_processing",
                            "real_time",
                            "batch_processing",
                            "general",
                        ],
                        "default": "general",
                        "description": "Performance context for analysis",
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Performance areas to focus on",
                        "default": [
                            "time_complexity",
                            "space_complexity",
                            "io_operations",
                            "database_queries",
                        ],
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="generate_api_documentation",
            description="Extract and generate API documentation from code using local LLM. Creates formatted docs with examples.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code containing API definitions",
                    },
                    "doc_format": {
                        "type": "string",
                        "enum": ["openapi", "markdown", "jsdoc", "rustdoc", "sphinx"],
                        "default": "markdown",
                        "description": "Documentation format to generate",
                    },
                    "include_examples": {
                        "type": "boolean",
                        "description": "Include usage examples in documentation",
                        "default": True,
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="generate_integration_tests",
            description="Create integration test suites using local LLM. Generates comprehensive tests for API endpoints and component interactions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to generate integration tests for",
                    },
                    "test_scenarios": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Test scenarios to cover",
                        "default": [
                            "happy_path",
                            "error_cases",
                            "edge_cases",
                            "authentication",
                        ],
                    },
                    "framework": {
                        "type": "string",
                        "enum": [
                            "pytest",
                            "unittest",
                            "jest",
                            "supertest",
                            "testcontainers",
                        ],
                        "default": "pytest",
                        "description": "Testing framework to use",
                    },
                    "include_fixtures": {
                        "type": "boolean",
                        "description": "Include test data fixtures",
                        "default": True,
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="security_scan_code",
            description="Detect security vulnerabilities in code using local LLM. Identifies common security issues with fix suggestions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to scan for security issues",
                    },
                    "vulnerability_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of vulnerabilities to check for",
                        "default": [
                            "injection",
                            "authentication",
                            "authorization",
                            "crypto",
                            "input_validation",
                        ],
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "include_fixes": {
                        "type": "boolean",
                        "description": "Include fix suggestions",
                        "default": True,
                    },
                    "severity_threshold": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium",
                        "description": "Minimum severity level to report",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="generate_unit_test_fixtures",
            description="Create test data and mock objects using local LLM. Generates realistic test fixtures for unit testing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_under_test": {
                        "type": "string",
                        "description": "Code that needs test fixtures",
                    },
                    "fixture_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of fixtures to generate",
                        "default": [
                            "mock_data",
                            "test_objects",
                            "api_responses",
                            "database_records",
                        ],
                    },
                    "framework": {
                        "type": "string",
                        "enum": ["pytest", "unittest", "jest", "mockito", "sinon"],
                        "default": "pytest",
                        "description": "Testing framework for fixtures",
                    },
                    "data_realism": {
                        "type": "string",
                        "enum": ["simple", "realistic", "comprehensive"],
                        "default": "realistic",
                        "description": "Level of realism for generated data",
                    },
                },
                "required": ["code_under_test"],
            },
        ),
        Tool(
            name="add_type_annotations",
            description="Add type hints to dynamically typed code using local LLM. Improves code maintainability and IDE support.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to add type annotations to",
                    },
                    "annotation_style": {
                        "type": "string",
                        "enum": ["basic", "comprehensive", "gradual"],
                        "default": "comprehensive",
                        "description": "Level of type annotation detail",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "typescript", "javascript"],
                        "default": "python",
                        "description": "Programming language",
                    },
                    "include_generics": {
                        "type": "boolean",
                        "description": "Include generic type parameters",
                        "default": True,
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="optimize_imports",
            description="Clean up and optimize import statements using local LLM. Removes unused imports, sorts, and groups them properly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code with imports to optimize",
                    },
                    "optimization_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of import optimization",
                        "default": ["remove_unused", "sort", "group", "add_missing"],
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "style_guide": {
                        "type": "string",
                        "enum": ["pep8", "google", "black", "isort", "eslint"],
                        "default": "pep8",
                        "description": "Import style guide to follow",
                    },
                },
                "required": ["code"],
            },
        ),
    ]
    log_info(f"Returning {len(tools)} tools")
    return tools


# ========== TOOL IMPLEMENTATIONS ==========
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    start_time = time.time()
    log_info(f"call_tool() invoked: {name}")
    log_debug(f"Arguments: {json.dumps(arguments, indent=2)}")

    try:
        if name == "health_check":
            checks = {}

            # Check vLLM connection
            try:
                client = await vllm_client.get_client()
                response = await client.get(
                    CONFIG.vllm.api_url.replace("/chat/completions", "/models")
                )
                checks["vllm_connection"] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time": response.elapsed.total_seconds()
                    if hasattr(response, "elapsed")
                    else 0,
                }
            except Exception as e:
                checks["vllm_connection"] = {"status": "unhealthy", "error": str(e)}

            # Check disk space
            try:
                statvfs = os.statvfs(".")
                free_space = statvfs.f_frsize * statvfs.f_bavail
                checks["disk_space"] = {
                    "free_bytes": free_space,
                    "free_gb": round(free_space / (1024**3), 2),
                }
            except Exception as e:
                checks["disk_space"] = {"error": str(e)}

            # Get metrics
            checks["metrics"] = metrics_collector.get_stats()

            # Configuration summary
            checks["configuration"] = {
                "caching_enabled": CONFIG.features.caching,
                "metrics_enabled": CONFIG.features.metrics,
                "auto_backup_enabled": CONFIG.features.auto_backup,
                "allowed_paths": len(CONFIG.security.allowed_paths),
            }

            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=json.dumps(checks, indent=2))]

        elif name == "generate_simple_code":
            language = arguments.get("language", "python")

            prompt = f"""You are a code generator. Generate clean, working {language} code for the following request.
Only output the code, no explanations unless asked.

Request: {arguments['prompt']}"""

            log_info("Calling vLLM API for generate_simple_code")
            code = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(code)} characters of code")
            metrics_collector.record_execution(
                name, start_time, True, tokens_used=len(code.split())
            )
            return [TextContent(type="text", text=code)]

        elif name == "complete_code":
            prompt = f"""Complete the following code according to the instruction.

Code:
{arguments['code_context']}

Instruction: {arguments['instruction']}

Provide only the completion, maintaining the existing code style."""

            log_info("Calling vLLM API for complete_code")
            completion = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(completion)} characters of completion")
            metrics_collector.record_execution(
                name, start_time, True, tokens_used=len(completion.split())
            )
            return [TextContent(type="text", text=completion)]

        elif name == "explain_code":
            detail = (
                "briefly" if arguments.get("detail_level") == "brief" else "in detail"
            )
            prompt = f"""Explain {detail} what this code does:

{arguments['code']}"""

            log_info("Calling vLLM API for explain_code")
            explanation = await call_vllm_api(prompt, "explanation")

            log_info(f"Generated {len(explanation)} characters of explanation")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=explanation)]

        elif name == "analyze_codebase":
            directory = arguments.get("directory", ".")
            analysis_type = arguments.get("analysis_type", "structure")

            # Validate directory path
            try:
                safe_dir = safe_path(".", directory)
            except ValueError as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, str(e))

            # Collect codebase information
            try:
                file_info = []
                for root, dirs, files in os.walk(safe_dir):
                    for file in files:
                        if any(
                            file.endswith(ext)
                            for ext_list in [
                                config["file_extensions"]
                                for config in LANGUAGE_CONFIGS.values()
                            ]
                            for ext in ext_list
                        ):
                            file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(file_path, safe_dir)
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    lines = len(f.readlines())
                                file_info.append(
                                    {"path": relative_path, "lines": lines}
                                )
                            except:
                                continue

                # Detect primary language
                primary_language = detect_project_language(safe_dir)

                prompt = f"""Analyze this {primary_language} codebase for {analysis_type}.

Files and structure:
{json.dumps(file_info[:50], indent=2)}

Analysis type: {analysis_type}

Provide insights about:
- Overall architecture and organization
- Code quality indicators
- Potential improvements
- Patterns and anti-patterns observed
- Recommendations for the development team

Total files analyzed: {len(file_info)}
Primary language: {primary_language}"""

                log_info(f"Analyzing codebase: {len(file_info)} files")
                analysis = await call_vllm_api(prompt, "analysis")

                result = {
                    "analysis": analysis,
                    "metadata": {
                        "directory": directory,
                        "files_found": len(file_info),
                        "primary_language": primary_language,
                        "analysis_type": analysis_type,
                    },
                }

                metrics_collector.record_execution(name, start_time, True)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="analysis_error"
                )
                return create_error_response(
                    name, f"Codebase analysis failed: {str(e)}"
                )

        elif name == "detect_code_smells":
            language = arguments.get("language", "python")

            prompt = f"""Analyze this {language} code for potential quality issues and code smells.

Code to analyze:
{arguments['code']}

Look for:
- Code duplication
- Long methods/functions
- Complex conditionals
- Poor naming conventions
- Missing error handling
- Performance issues
- Security vulnerabilities
- Maintainability concerns

Provide specific recommendations for improvement with examples where possible."""

            log_info("Analyzing code for smells")
            analysis = await call_vllm_api(prompt, "analysis")

            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=analysis)]

        elif name == "git_smart_commit":
            auto_push = arguments.get("auto_push", True)
            commit_type = arguments.get("commit_type", "auto")

            try:
                # Get git diff
                diff_result = subprocess.run(
                    ["git", "diff", "--cached"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                if not diff_result.stdout.strip():
                    # Nothing staged, check working directory
                    diff_result = subprocess.run(
                        ["git", "diff"], capture_output=True, text=True, check=True
                    )

                    if not diff_result.stdout.strip():
                        metrics_collector.record_execution(
                            name, start_time, False, error_type="no_changes"
                        )
                        return create_error_response(name, "No changes to commit")

                    # Auto-stage all changes
                    subprocess.run(["git", "add", "."], check=True)

                    # Get staged diff
                    diff_result = subprocess.run(
                        ["git", "diff", "--cached"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                # Generate commit message
                type_instruction = (
                    f"Use commit type '{commit_type}'"
                    if commit_type != "auto"
                    else "Choose appropriate commit type (feat, fix, docs, style, refactor, test, chore)"
                )

                prompt = f"""Generate a conventional commit message for these changes.

{type_instruction}.

Git diff:
{diff_result.stdout[:3000]}

Format: type(scope): description

Provide only the commit message, no explanations. Make it concise but descriptive."""

                log_info("Generating smart commit message")
                commit_message = await call_vllm_api(prompt, "git_commit")
                commit_message = commit_message.strip()

                # Execute commit
                commit_result = subprocess.run(
                    ["git", "commit", "-m", commit_message],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                response_data = {
                    "ok": True,
                    "commit_message": commit_message,
                    "commit_output": commit_result.stdout.strip(),
                }

                # Auto-push if enabled
                if auto_push:
                    try:
                        push_result = subprocess.run(
                            ["git", "push", "origin", "HEAD"],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        response_data["push"] = {
                            "ok": True,
                            "output": push_result.stdout.strip(),
                        }
                    except subprocess.CalledProcessError as e:
                        response_data["push"] = {"ok": False, "error": e.stderr}

                metrics_collector.record_execution(name, start_time, True)
                return [
                    TextContent(type="text", text=json.dumps(response_data, indent=2))
                ]

            except subprocess.CalledProcessError as e:
                error_msg = f"Git operation failed: {e.stderr}"
                metrics_collector.record_execution(
                    name, start_time, False, error_type="git_error"
                )
                return create_error_response(name, error_msg)

        elif name == "generate_docstrings":
            style = arguments.get("style", "google")
            language = arguments.get("language", "python")
            prompt = f"""Add {style}-style docstrings to this {language} code. Return the complete code with docstrings added.

{arguments['code']}

Follow {style} documentation standards for {language}. Include parameter descriptions, return values, and any exceptions that might be raised."""

            log_info("Calling vLLM API for generate_docstrings")
            documented_code = await call_vllm_api(prompt, "documentation")

            log_info(f"Generated {len(documented_code)} characters of documented code")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=documented_code)]

        elif name == "generate_tests":
            framework = arguments.get("test_framework", "pytest")
            coverage = arguments.get("coverage_level", "standard")

            coverage_desc = {
                "basic": "basic happy path tests",
                "standard": "happy path tests plus common edge cases",
                "comprehensive": "comprehensive tests including happy path, edge cases, and error conditions",
            }

            prompt = f"""Generate {coverage_desc[coverage]} using {framework} for the following code.

Code to test:
{arguments['code']}

Generate complete, runnable test code."""

            log_info("Calling vLLM API for generate_tests")
            tests = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(tests)} characters of tests")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=tests)]

        elif name == "refactor_simple_code":
            context = arguments.get("additional_context", "")
            context_str = f"\n\nAdditional context: {context}" if context else ""

            prompt = f"""Refactor the following code using this refactoring pattern: {arguments['refactor_type']}
{context_str}

Original code:
{arguments['code']}

Provide the refactored code, maintaining functionality."""

            log_info("Calling vLLM API for refactor_simple_code")
            refactored = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(refactored)} characters of refactored code")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=refactored)]

        elif name == "fix_simple_bugs":
            context = arguments.get("context", "")
            context_str = f"\n\nAdditional context: {context}" if context else ""

            prompt = f"""Fix the bug in this code.

Error message: {arguments['error_message']}
{context_str}

Code with bug:
{arguments['code']}

Provide the corrected code with a brief explanation of the fix."""

            log_info("Calling vLLM API for fix_simple_bugs")
            fixed_code = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(fixed_code)} characters of fixed code")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=fixed_code)]

        elif name == "convert_code_format":
            prompt = f"""Convert this code from {arguments['from_format']} to {arguments['to_format']}.

Original code:
{arguments['code']}

Provide only the converted code."""

            log_info("Calling vLLM API for convert_code_format")
            converted = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(converted)} characters of converted code")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=converted)]

        elif name == "generate_boilerplate_file":
            options_str = json.dumps(arguments.get("options", {}), indent=2)

            prompt = f"""Generate a complete {arguments['file_type']} file in {arguments['language']}.

Options: {options_str}

Generate production-ready, well-structured boilerplate code."""

            log_info("Calling vLLM API for generate_boilerplate_file")
            boilerplate = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(boilerplate)} characters of boilerplate")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=boilerplate)]

        elif name == "improve_code_style":
            style_guide = arguments.get("style_guide", "pep8")
            language = arguments.get("language", "python")

            prompt = f"""Improve the code style following {style_guide} guidelines for {language}.
Focus on: naming conventions, formatting, readability, and best practices.

Original code:
{arguments['code']}

Provide the improved code."""

            log_info("Calling vLLM API for improve_code_style")
            improved = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(improved)} characters of improved code")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=improved)]

        elif name == "generate_schema":
            language = arguments.get("language", "python")

            prompt = f"""Generate a {arguments['schema_type']} schema in {language} based on this description:

{arguments['description']}

Generate complete, well-typed schema code."""

            log_info("Calling vLLM API for generate_schema")
            schema = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(schema)} characters of schema")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=schema)]

        elif name == "generate_git_commit_message":
            commit_type = arguments.get("commit_type", "auto")
            scope = arguments.get("scope", "")

            type_instruction = (
                f"Use commit type '{commit_type}'"
                if commit_type != "auto"
                else "Choose appropriate commit type (feat, fix, docs, style, refactor, test, chore)"
            )
            scope_instruction = f" with scope '{scope}'" if scope else ""

            prompt = f"""Generate a conventional commit message for these changes.

{type_instruction}{scope_instruction}.

Changes summary:
{arguments['changes_summary']}

Format: type(scope): description

Provide only the commit message, no explanations."""

            log_info("Calling vLLM API for generate_git_commit_message")
            commit_message = await call_vllm_api(prompt, "git_commit")
            commit_message = commit_message.strip()

            log_info(f"Generated commit message: {commit_message[:50]}...")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=commit_message)]

        elif name == "generate_gitignore":
            frameworks = arguments.get("frameworks", [])
            custom_patterns = arguments.get("custom_patterns", [])

            frameworks_str = ", ".join(frameworks) if frameworks else "none"
            custom_str = "\n".join(custom_patterns) if custom_patterns else "none"

            prompt = f"""Generate a comprehensive .gitignore file for {arguments['language']}.

Additional frameworks/tools: {frameworks_str}
Custom patterns to include: {custom_str}

Include common patterns for the language, IDE files, OS files, and build artifacts.
Provide only the .gitignore content, no explanations."""

            log_info("Calling vLLM API for generate_gitignore")
            gitignore = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(gitignore)} characters of .gitignore")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=gitignore)]

        elif name == "generate_github_workflow":
            language = arguments.get("language", "python")
            triggers = arguments.get("triggers", ["push", "pull_request"])
            custom_requirements = arguments.get("custom_requirements", "")

            triggers_str = ", ".join(triggers)
            custom_str = (
                f"\n\nAdditional requirements: {custom_requirements}"
                if custom_requirements
                else ""
            )

            prompt = f"""Generate a GitHub Actions workflow file for {arguments['workflow_type']} in {language}.

Triggers: {triggers_str}{custom_str}

Generate a complete, production-ready .github/workflows/[name].yml file.
Include appropriate steps for the workflow type and language.
Provide only the YAML content, no explanations."""

            log_info("Calling vLLM API for generate_github_workflow")
            workflow = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(workflow)} characters of workflow")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=workflow)]

        elif name == "generate_pr_description":
            context = arguments.get("context", "")
            breaking_changes = arguments.get("breaking_changes", False)

            context_str = f"\n\nContext: {context}" if context else ""
            breaking_str = (
                "\n\n⚠️ This PR contains BREAKING CHANGES" if breaking_changes else ""
            )

            prompt = f"""Generate a comprehensive pull request description for a {arguments['pr_type']} PR.

Changes summary:
{arguments['changes_summary']}{context_str}{breaking_str}

Include:
- Brief summary
- What changed
- Why the change was needed
- Testing notes (if applicable)
- Checklist for reviewers

Use markdown formatting."""

            log_info("Calling vLLM API for generate_pr_description")
            pr_description = await call_vllm_api(prompt, "documentation")

            log_info(f"Generated {len(pr_description)} characters of PR description")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=pr_description)]

        elif name == "git_status":
            porcelain = arguments.get("porcelain", True)
            cmd = ["git", "status"]
            if porcelain:
                cmd.extend(["--porcelain", "-b"])

            log_info(f"Executing: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                log_info(f"Git status completed successfully")

                # Parse porcelain output for structured response
                if porcelain:
                    lines = output.split("\n")
                    branch_line = lines[0] if lines else ""
                    file_lines = lines[1:] if len(lines) > 1 else []

                    files = {
                        "modified": [],
                        "added": [],
                        "deleted": [],
                        "untracked": [],
                    }

                    for line in file_lines:
                        if not line.strip():
                            continue
                        status = line[:2]
                        filename = line[3:]

                        if status.startswith("M"):
                            files["modified"].append(filename)
                        elif status.startswith("A"):
                            files["added"].append(filename)
                        elif status.startswith("D"):
                            files["deleted"].append(filename)
                        elif status.startswith("??"):
                            files["untracked"].append(filename)

                    response_data = {
                        "ok": True,
                        "output": output,
                        "branch": branch_line,
                        "files": files,
                        "cmd": " ".join(cmd),
                    }
                    metrics_collector.record_execution(name, start_time, True)
                    return [
                        TextContent(
                            type="text", text=json.dumps(response_data, indent=2)
                        )
                    ]
                else:
                    metrics_collector.record_execution(name, start_time, True)
                    return [TextContent(type="text", text=output)]

            except subprocess.CalledProcessError as e:
                error_msg = f"Git status failed: {e.stderr}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="git_error"
                )
                return create_error_response(name, error_msg)

        elif name == "git_add":
            files = arguments.get("files", [])
            if not files:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="missing_args"
                )
                return create_error_response(name, "No files specified")

            cmd = ["git", "add"] + files
            log_info(f"Executing: {' '.join(cmd)}")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                log_info(f"Git add completed successfully")
                response_data = {
                    "ok": True,
                    "output": result.stdout.strip(),
                    "cmd": " ".join(cmd),
                }
                metrics_collector.record_execution(name, start_time, True)
                return [
                    TextContent(type="text", text=json.dumps(response_data, indent=2))
                ]

            except subprocess.CalledProcessError as e:
                error_msg = f"Git add failed: {e.stderr}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="git_error"
                )
                return create_error_response(name, error_msg)

        elif name == "git_commit":
            message = arguments.get("message", "")
            auto_push = arguments.get("auto_push", True)

            if not message:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="missing_args"
                )
                return create_error_response(name, "Commit message required")

            cmd = ["git", "commit", "-m", message]
            log_info(f"Executing: git commit -m '[message]'")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                log_info(f"Git commit completed successfully")

                response_data = {
                    "ok": True,
                    "output": result.stdout.strip(),
                    "message": message,
                    "cmd": f"git commit -m {message}",
                }

                # Auto-push if enabled
                if auto_push:
                    push_cmd = ["git", "push", "origin", "HEAD"]
                    log_info("Auto-pushing to origin")
                    try:
                        push_result = subprocess.run(
                            push_cmd, capture_output=True, text=True, check=True
                        )
                        response_data["push"] = {
                            "ok": True,
                            "output": push_result.stdout.strip(),
                            "cmd": " ".join(push_cmd),
                        }
                        log_info("Git push completed successfully")
                    except subprocess.CalledProcessError as e:
                        response_data["push"] = {
                            "ok": False,
                            "error": f"Push failed: {e.stderr}",
                            "cmd": " ".join(push_cmd),
                        }
                        log_error(f"Git push failed: {e.stderr}")

                metrics_collector.record_execution(name, start_time, True)
                return [
                    TextContent(type="text", text=json.dumps(response_data, indent=2))
                ]

            except subprocess.CalledProcessError as e:
                error_msg = f"Git commit failed: {e.stderr}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="git_error"
                )
                return create_error_response(name, error_msg)

        elif name == "git_diff":
            staged = arguments.get("staged", False)
            files = arguments.get("files", [])

            cmd = ["git", "diff"]
            if staged:
                cmd.append("--cached")
            cmd.extend(files)

            log_info(f"Executing: {' '.join(cmd)}")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                log_info(f"Git diff completed successfully")
                metrics_collector.record_execution(name, start_time, True)
                return [
                    TextContent(
                        type="text",
                        text=output if output else "No differences found",
                    )
                ]

            except subprocess.CalledProcessError as e:
                error_msg = f"Git diff failed: {e.stderr}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="git_error"
                )
                return create_error_response(name, error_msg)

        elif name == "git_log":
            limit = arguments.get("limit", 10)
            oneline = arguments.get("oneline", True)

            cmd = ["git", "log", f"-{limit}"]
            if oneline:
                cmd.append("--oneline")

            log_info(f"Executing: {' '.join(cmd)}")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                log_info(f"Git log completed successfully")
                metrics_collector.record_execution(name, start_time, True)
                return [
                    TextContent(
                        type="text", text=output if output else "No commits found"
                    )
                ]

            except subprocess.CalledProcessError as e:
                error_msg = f"Git log failed: {e.stderr}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="git_error"
                )
                return create_error_response(name, error_msg)

        elif name == "create_config_file":
            file_type = arguments["file_type"]
            path = arguments["path"]
            options = arguments.get("options", {})
            custom_prompt = arguments.get("custom_prompt", "")

            # Validate path
            try:
                safe_file_path = safe_path(".", path)
            except ValueError as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, str(e))

            if file_type == "custom" and not custom_prompt:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="missing_args"
                )
                return create_error_response(
                    name, "Custom prompt required for custom file type"
                )

            # Generate file content using LLM
            if file_type == "custom":
                prompt = custom_prompt
            else:
                options_str = json.dumps(options, indent=2) if options else "none"
                prompt = f"""Generate a {file_type} configuration file.

Options: {options_str}

Generate complete, production-ready file content. Include comments where appropriate.
Provide only the file content, no explanations."""

            log_info(f"Generating {file_type} config file")
            content = await call_vllm_api(prompt, "code_generation")

            # Create backup if file exists
            backup_path = create_backup(safe_file_path)

            # Write file
            try:
                os.makedirs(os.path.dirname(safe_file_path), exist_ok=True)
                with open(safe_file_path, "w") as f:
                    f.write(content)

                log_info(f"Created config file: {safe_file_path}")
                response_data = {
                    "ok": True,
                    "path": safe_file_path,
                    "file_type": file_type,
                    "content_length": len(content),
                }
                if backup_path:
                    response_data["backup_created"] = backup_path

                metrics_collector.record_execution(name, start_time, True)
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(response_data, indent=2),
                    )
                ]

            except Exception as e:
                error_msg = f"Failed to write file {safe_file_path}: {str(e)}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="file_error"
                )
                return create_error_response(name, error_msg)

        elif name == "create_directory_structure":
            structure_type = arguments["structure_type"]
            base_path = arguments["base_path"]
            project_name = arguments["project_name"]
            options = arguments.get("options", {})

            # Validate base path
            try:
                safe_base_path = safe_path(".", base_path)
            except ValueError as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, str(e))

            options_str = (
                json.dumps(options, indent=2) if options else "standard options"
            )

            prompt = f"""Generate a directory structure for a {structure_type} project named '{project_name}'.

Options: {options_str}

Provide a JSON list of directory paths to create (relative to base path).
Include standard directories for this project type.
Format: ["dir1", "dir2/subdir", "dir3"]

Provide only the JSON array, no explanations."""

            log_info(f"Generating {structure_type} directory structure")
            directories_json = await call_vllm_api(prompt, "code_generation")
            directories_json = directories_json.strip()

            try:
                # Parse JSON response
                directories = json.loads(directories_json)
                created_dirs = []

                # Create directories
                for dir_path in directories:
                    full_path = os.path.join(safe_base_path, project_name, dir_path)
                    os.makedirs(full_path, exist_ok=True)
                    created_dirs.append(full_path)

                log_info(f"Created {len(created_dirs)} directories")
                response_data = {
                    "ok": True,
                    "project_path": os.path.join(safe_base_path, project_name),
                    "directories_created": created_dirs,
                    "structure_type": structure_type,
                }
                metrics_collector.record_execution(name, start_time, True)
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(response_data, indent=2),
                    )
                ]

            except (json.JSONDecodeError, Exception) as e:
                error_msg = f"Failed to create directory structure: {str(e)}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="structure_error"
                )
                return create_error_response(
                    name, error_msg, {"raw_response": directories_json}
                )

        elif name == "create_github_issue":
            repository = arguments["repository"]
            issue_type = arguments["issue_type"]
            title = arguments["title"]
            description = arguments["description"]
            labels = arguments.get("labels", [])

            # Generate issue body using LLM
            prompt = f"""Generate a comprehensive GitHub issue body for a {issue_type} issue.

Title: {title}
Description/Context: {description}

Generate a well-structured issue body with:
- Clear problem description
- Steps to reproduce (if bug)
- Expected vs actual behavior (if bug)
- Acceptance criteria (if feature)
- Additional context

Use markdown formatting. Provide only the issue body content."""

            log_info(f"Generating GitHub issue body for {repository}")
            issue_body = await call_vllm_api(prompt, "documentation")

            log_info(f"Generated issue content for {repository}")
            response_data = {
                "ok": True,
                "repository": repository,
                "title": title,
                "body": issue_body,
                "labels": labels,
                "issue_type": issue_type,
                "note": "Issue content generated. Use GitHub MCP server to actually create the issue.",
            }
            metrics_collector.record_execution(name, start_time, True)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(response_data, indent=2),
                )
            ]

        elif name == "create_github_pr":
            repository = arguments["repository"]
            head_branch = arguments["head_branch"]
            base_branch = arguments.get("base_branch", "main")
            title = arguments["title"]
            changes_summary = arguments["changes_summary"]
            pr_type = arguments["pr_type"]

            # Generate PR description using LLM
            prompt = f"""Generate a comprehensive GitHub pull request description for a {pr_type} PR.

Title: {title}
Changes Summary: {changes_summary}
Branch: {head_branch} -> {base_branch}

Generate a well-structured PR description with:
- Brief summary of changes
- What was changed and why
- Testing performed
- Checklist for reviewers
- Any breaking changes or migration notes

Use markdown formatting. Provide only the PR description content."""

            log_info(f"Generating GitHub PR description for {repository}")
            pr_body = await call_vllm_api(prompt, "documentation")

            log_info(f"Generated PR content for {repository}")
            response_data = {
                "ok": True,
                "repository": repository,
                "title": title,
                "body": pr_body,
                "head_branch": head_branch,
                "base_branch": base_branch,
                "pr_type": pr_type,
                "note": "PR content generated. Use GitHub MCP server to actually create the pull request.",
            }
            metrics_collector.record_execution(name, start_time, True)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(response_data, indent=2),
                )
            ]

        elif name == "execute_dev_command":
            command_type = arguments["command_type"]
            args = arguments.get("arguments", [])
            working_dir = arguments.get("working_directory", ".")
            custom_command = arguments.get("custom_command", "")

            # Validate working directory
            try:
                safe_working_dir = safe_path(".", working_dir)
            except ValueError as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, str(e))

            # Map command types to actual commands
            command_map = {
                "npm_install": ["npm", "install"] + args,
                "pip_install": ["pip", "install"] + args,
                "cargo_build": ["cargo", "build"] + args,
                "go_mod_tidy": ["go", "mod", "tidy"] + args,
                "make": ["make"] + args,
                "test": ["npm", "test"] + args
                if os.path.exists(os.path.join(safe_working_dir, "package.json"))
                else ["python", "-m", "pytest"] + args,
            }

            if command_type == "custom":
                if not custom_command:
                    metrics_collector.record_execution(
                        name, start_time, False, error_type="missing_args"
                    )
                    return create_error_response(name, "Custom command required")
                cmd = custom_command.split() + args
            else:
                cmd = command_map.get(command_type)
                if not cmd:
                    metrics_collector.record_execution(
                        name, start_time, False, error_type="invalid_command"
                    )
                    return create_error_response(
                        name, f"Unknown command type: {command_type}"
                    )

            # Validate command
            if not validate_command(cmd):
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, f"Command not allowed: {cmd[0]}")

            log_info(f"Executing: {' '.join(cmd)} in {safe_working_dir}")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=safe_working_dir,
                    timeout=300,
                )

                response_data = {
                    "ok": result.returncode == 0,
                    "command": " ".join(cmd),
                    "working_directory": safe_working_dir,
                    "return_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }

                if result.returncode != 0:
                    log_error(f"Command failed with return code {result.returncode}")
                    metrics_collector.record_execution(
                        name, start_time, False, error_type="command_failed"
                    )
                else:
                    log_info(f"Command executed successfully")
                    metrics_collector.record_execution(name, start_time, True)

                return [
                    TextContent(type="text", text=json.dumps(response_data, indent=2))
                ]

            except subprocess.TimeoutExpired:
                error_msg = "Command timed out after 5 minutes"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="timeout"
                )
                return create_error_response(name, error_msg)
            except Exception as e:
                error_msg = f"Command execution failed: {str(e)}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="execution_error"
                )
                return create_error_response(name, error_msg)

        elif name == "create_database_schema":
            database_path = arguments["database_path"]
            schema_description = arguments["schema_description"]
            tables = arguments.get("tables", [])

            # Validate database path
            try:
                safe_db_path = safe_path(".", database_path)
            except ValueError as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, str(e))

            tables_info = (
                "\n".join(
                    [
                        f"- {table.get('name', 'unnamed')}: {table.get('description', 'no description')}"
                        for table in tables
                    ]
                )
                if tables
                else "No specific tables mentioned"
            )

            prompt = f"""Generate SQLite CREATE TABLE statements for this database schema.

Schema Description: {schema_description}

Tables:
{tables_info}

Generate complete CREATE TABLE statements with:
- Appropriate data types
- Primary keys
- Foreign key relationships where applicable
- Indexes for common queries
- Comments explaining the schema

Provide only the SQL statements, properly formatted."""

            log_info(f"Generating database schema for {safe_db_path}")
            sql_schema = await call_vllm_api(prompt, "code_generation")

            response_data = {
                "ok": True,
                "database_path": safe_db_path,
                "schema_sql": sql_schema,
                "tables_count": len(tables),
                "note": "Schema SQL generated. Use SQLite MCP server to actually execute the schema creation.",
            }

            log_info(f"Generated schema SQL for {safe_db_path}")
            metrics_collector.record_execution(name, start_time, True)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(response_data, indent=2),
                )
            ]

        elif name == "generate_sql_queries":
            query_type = arguments["query_type"]
            table_info = arguments["table_info"]
            requirements = arguments["requirements"]
            execute = arguments.get("execute", False)
            database_path = arguments.get("database_path", "")

            prompt = f"""Generate a {query_type.upper()} SQL query based on these requirements.

Table Information: {table_info}
Requirements: {requirements}

Generate a complete, optimized SQL query with:
- Proper syntax for SQLite
- Comments explaining the logic
- Appropriate WHERE clauses, JOINs, etc.
- Error handling considerations

Provide only the SQL query, properly formatted."""

            log_info(f"Generating {query_type} SQL query")
            sql_query = await call_vllm_api(prompt, "code_generation")

            response_data = {
                "ok": True,
                "query_type": query_type,
                "sql_query": sql_query,
                "requirements": requirements,
            }

            if execute and database_path:
                response_data[
                    "note"
                ] = "Query generated. Use SQLite MCP server to execute if needed."
                response_data["database_path"] = database_path

            log_info(f"Generated {query_type} SQL query")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

        elif name == "validate":
            files = arguments.get("files", [])
            working_dir = arguments.get("working_directory", ".")

            # Validate working directory
            try:
                safe_working_dir = safe_path(".", working_dir)
            except ValueError as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, str(e))

            if not os.path.exists(safe_working_dir):
                metrics_collector.record_execution(
                    name, start_time, False, error_type="path_not_found"
                )
                return create_error_response(
                    name, f"Working directory does not exist: {safe_working_dir}"
                )

            # Validate files exist if specified
            if files:
                missing_files = []
                for file_path in files:
                    full_path = os.path.join(safe_working_dir, file_path)
                    if not os.path.exists(full_path):
                        missing_files.append(file_path)

                if missing_files:
                    metrics_collector.record_execution(
                        name, start_time, False, error_type="files_not_found"
                    )
                    return create_error_response(
                        name, f"Files not found: {', '.join(missing_files)}"
                    )

            # Build pre-commit command
            if files:
                cmd = ["pre-commit", "run", "--files"] + files
            else:
                cmd = ["pre-commit", "run", "--all-files"]

            # Validate command
            if not validate_command(cmd):
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, "Pre-commit command not allowed")

            log_info(f"Executing: {' '.join(cmd)} in {safe_working_dir}")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=safe_working_dir,
                    timeout=300,
                )

                response_data = {
                    "ok": result.returncode == 0,
                    "command": " ".join(cmd),
                    "working_directory": safe_working_dir,
                    "return_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "files_checked": files if files else "all files",
                }

                if result.returncode != 0:
                    log_error(
                        f"Pre-commit validation failed with return code {result.returncode}"
                    )
                    metrics_collector.record_execution(
                        name, start_time, False, error_type="validation_failed"
                    )
                else:
                    log_info(f"Pre-commit validation passed")
                    metrics_collector.record_execution(name, start_time, True)

                return [
                    TextContent(type="text", text=json.dumps(response_data, indent=2))
                ]

            except subprocess.TimeoutExpired:
                error_msg = "Pre-commit validation timed out after 5 minutes"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="timeout"
                )
                return create_error_response(name, error_msg)
            except Exception as e:
                error_msg = f"Pre-commit validation failed: {str(e)}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="validation_error"
                )
                return create_error_response(name, error_msg)

        elif name == "validate_correct":
            files = arguments.get("files", [])
            working_dir = arguments.get("working_directory", ".")
            max_corrections = arguments.get("max_corrections", 10)

            # Validate working directory
            try:
                safe_working_dir = safe_path(".", working_dir)
            except ValueError as e:
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, str(e))

            if not os.path.exists(safe_working_dir):
                metrics_collector.record_execution(
                    name, start_time, False, error_type="path_not_found"
                )
                return create_error_response(
                    name, f"Working directory does not exist: {safe_working_dir}"
                )

            # Validate files exist if specified
            if files:
                missing_files = []
                for file_path in files:
                    full_path = os.path.join(safe_working_dir, file_path)
                    if not os.path.exists(full_path):
                        missing_files.append(file_path)

                if missing_files:
                    metrics_collector.record_execution(
                        name, start_time, False, error_type="files_not_found"
                    )
                    return create_error_response(
                        name, f"Files not found: {', '.join(missing_files)}"
                    )

            # First run validation to get issues
            if files:
                cmd = ["pre-commit", "run", "--files"] + files
            else:
                cmd = ["pre-commit", "run", "--all-files"]

            # Validate command
            if not validate_command(cmd):
                metrics_collector.record_execution(
                    name, start_time, False, error_type="security_error"
                )
                return create_error_response(name, "Pre-commit command not allowed")

            log_info(f"Running validation: {' '.join(cmd)} in {safe_working_dir}")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=safe_working_dir,
                    timeout=300,
                )

                if result.returncode == 0:
                    response_data = {
                        "ok": True,
                        "message": "No validation issues found",
                        "command": " ".join(cmd),
                        "working_directory": safe_working_dir,
                    }
                    metrics_collector.record_execution(name, start_time, True)
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps(response_data, indent=2),
                        )
                    ]

                # Parse pre-commit output to identify files with issues
                validation_output = result.stdout + result.stderr

                # Use LLM to analyze validation output and suggest corrections
                prompt = f"""Analyze this pre-commit validation output and identify specific files that need correction:

{validation_output}

For each file that has issues, determine:
1. The exact file path
2. What type of issues were found (formatting, imports, linting, etc.)
3. Whether these are auto-fixable issues like:
   - Code formatting (black, prettier, etc.)
   - Import sorting (isort)
   - Trailing whitespace
   - Line ending issues
   - Simple linting fixes

Do NOT mark as auto-fixable:
   - Logic errors
   - Type errors requiring code changes
   - Missing dependencies
   - Complex refactoring needs

Format your response as valid JSON:
{{
  "files_with_issues": [
    {{
      "file": "exact/path/to/file.py",
      "issues": "specific description of what needs fixing",
      "auto_fixable": true
    }}
  ],
  "summary": "brief summary of validation results"
}}"""

                log_info("Analyzing validation output with LLM")
                analysis = await call_vllm_api(prompt, "analysis")

                try:
                    analysis_data = json.loads(analysis)
                    files_with_issues = analysis_data.get("files_with_issues", [])

                    corrections_made = []
                    corrections_count = 0

                    for file_info in files_with_issues[:max_corrections]:
                        if file_info.get("auto_fixable", False):
                            file_path = file_info["file"]
                            safe_file_path = os.path.join(safe_working_dir, file_path)

                            # Additional path validation
                            try:
                                safe_file_path = safe_path(safe_working_dir, file_path)
                            except ValueError:
                                corrections_made.append(
                                    {
                                        "file": file_path,
                                        "issues": file_info["issues"],
                                        "corrected": False,
                                        "error": "Path validation failed",
                                    }
                                )
                                continue

                            # Check file size
                            if not validate_file_size(safe_file_path):
                                corrections_made.append(
                                    {
                                        "file": file_path,
                                        "issues": file_info["issues"],
                                        "corrected": False,
                                        "error": "File too large",
                                    }
                                )
                                continue

                            # Read the file
                            try:
                                with open(safe_file_path, "r") as f:
                                    file_content = f.read()

                                # Create backup
                                backup_path = create_backup(safe_file_path)

                                # Use LLM to fix the issues
                                fix_prompt = f"""Fix the pre-commit validation issues in this file. Apply only the specific fixes needed:

File: {file_path}
Issues to fix: {file_info['issues']}

Original file content:
```
{file_content}
```

Validation output for context:
```
{validation_output}
```

Instructions:
1. Fix ONLY the specific issues mentioned
2. Do not make unnecessary changes to working code
3. Preserve the original logic and functionality
4. Apply standard formatting/linting fixes as needed
5. Return the complete corrected file content

Corrected file content:"""

                                log_info(f"Fixing issues in {file_path}")
                                corrected_content = await call_vllm_api(
                                    fix_prompt, "code_generation"
                                )
                                corrected_content = corrected_content.strip()

                                # Safety checks before writing
                                if not corrected_content:
                                    raise ValueError("LLM returned empty content")

                                if len(corrected_content) < len(file_content) * 0.5:
                                    raise ValueError(
                                        "LLM returned suspiciously short content"
                                    )

                                # Validate corrected content
                                validate_llm_response(corrected_content, file_content)

                                # Write the corrected content back
                                with open(safe_file_path, "w") as f:
                                    f.write(corrected_content)

                                corrections_made.append(
                                    {
                                        "file": file_path,
                                        "issues": file_info["issues"],
                                        "corrected": True,
                                        "backup_created": backup_path,
                                    }
                                )
                                corrections_count += 1

                            except Exception as e:
                                corrections_made.append(
                                    {
                                        "file": file_path,
                                        "issues": file_info["issues"],
                                        "corrected": False,
                                        "error": str(e),
                                    }
                                )
                        else:
                            corrections_made.append(
                                {
                                    "file": file_info["file"],
                                    "issues": file_info["issues"],
                                    "corrected": False,
                                    "reason": "requires manual intervention",
                                }
                            )

                    # Run validation again to check if issues are resolved
                    final_result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        cwd=safe_working_dir,
                        timeout=300,
                    )

                    response_data = {
                        "ok": True,
                        "validation_passed": final_result.returncode == 0,
                        "corrections_made": corrections_count,
                        "files_processed": corrections_made,
                        "analysis": analysis_data.get("summary", ""),
                        "final_validation": {
                            "return_code": final_result.returncode,
                            "stdout": final_result.stdout,
                            "stderr": final_result.stderr,
                        },
                    }

                    metrics_collector.record_execution(name, start_time, True)
                    return [
                        TextContent(
                            type="text", text=json.dumps(response_data, indent=2)
                        )
                    ]

                except json.JSONDecodeError:
                    error_msg = "Failed to parse LLM analysis"
                    log_error(error_msg)
                    metrics_collector.record_execution(
                        name, start_time, False, error_type="parse_error"
                    )
                    return create_error_response(
                        name,
                        error_msg,
                        {
                            "raw_analysis": analysis,
                            "validation_output": validation_output,
                        },
                    )

            except subprocess.TimeoutExpired:
                error_msg = "Pre-commit validation timed out after 5 minutes"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="timeout"
                )
                return create_error_response(name, error_msg)
            except Exception as e:
                error_msg = f"Validation and correction failed: {str(e)}"
                log_error(error_msg)
                metrics_collector.record_execution(
                    name, start_time, False, error_type="validation_error"
                )
                return create_error_response(name, error_msg)
        elif name == "generate_code_review":
            review_focus = arguments.get(
                "review_focus", ["style", "bugs", "performance", "maintainability"]
            )
            language = arguments.get("language", "python")
            severity_filter = arguments.get("severity_filter", "all")

            focus_areas = ", ".join(review_focus)

            prompt = f"""Perform a comprehensive code review of this {language} code diff/change.

Code to review:
{arguments['code_diff']}

Focus areas: {focus_areas}

Provide a structured code review with:
1. Overall assessment (summary of code quality)
2. Specific issues found with severity levels (HIGH/MEDIUM/LOW)
3. Positive aspects worth noting
4. Specific improvement suggestions with examples
5. Best practices recommendations

Format each issue as:
[SEVERITY] Line/Section: Description
Suggestion: Specific fix recommendation

Filter results to show {severity_filter} severity issues."""

            log_info("Performing code review analysis")
            review = await call_vllm_api(prompt, "analysis")

            log_info(f"Generated {len(review)} characters of code review")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=review)]

        elif name == "suggest_refactoring_opportunities":
            refactoring_types = arguments.get(
                "refactoring_types",
                [
                    "extract_method",
                    "reduce_complexity",
                    "remove_duplication",
                    "improve_naming",
                ],
            )
            complexity_threshold = arguments.get("complexity_threshold", 10)
            language = arguments.get("language", "python")

            refactoring_focus = ", ".join(refactoring_types)

            prompt = f"""Analyze this {language} code for refactoring opportunities.

Code to analyze:
{arguments['code']}

Refactoring types to consider: {refactoring_focus}
Complexity threshold: {complexity_threshold}

Provide ranked refactoring suggestions with:
1. Priority ranking (1-5, where 5 is highest priority)
2. Refactoring type and specific location
3. Current problem description
4. Proposed solution with code example
5. Benefits of the refactoring
6. Estimated effort level (Low/Medium/High)

Focus on practical, implementable improvements that will have meaningful impact on code quality, readability, and maintainability."""

            log_info("Analyzing code for refactoring opportunities")
            suggestions = await call_vllm_api(prompt, "analysis")

            log_info(
                f"Generated {len(suggestions)} characters of refactoring suggestions"
            )
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=suggestions)]

        elif name == "generate_performance_analysis":
            language = arguments.get("language", "python")
            performance_context = arguments.get("performance_context", "general")
            focus_areas = arguments.get(
                "focus_areas",
                [
                    "time_complexity",
                    "space_complexity",
                    "io_operations",
                    "database_queries",
                ],
            )

            focus_description = ", ".join(focus_areas)

            prompt = f"""Analyze this {language} code for performance bottlenecks and optimization opportunities.

Code to analyze:
{arguments['code']}

Performance context: {performance_context}
Focus areas: {focus_description}

Provide a detailed performance analysis with:
1. Performance bottleneck identification
2. Time/space complexity analysis
3. I/O operation efficiency assessment
4. Memory usage patterns
5. Specific optimization recommendations with code examples
6. Performance impact estimation (High/Medium/Low improvement)
7. Trade-offs and considerations for each optimization

Include both algorithmic improvements and language-specific optimizations appropriate for {performance_context} applications."""

            log_info("Performing performance analysis")
            analysis = await call_vllm_api(prompt, "analysis")

            log_info(f"Generated {len(analysis)} characters of performance analysis")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=analysis)]

        elif name == "generate_api_documentation":
            doc_format = arguments.get("doc_format", "markdown")
            include_examples = arguments.get("include_examples", True)
            language = arguments.get("language", "python")

            examples_instruction = (
                "Include detailed usage examples with request/response samples"
                if include_examples
                else "Focus on API specification without examples"
            )

            prompt = f"""Generate comprehensive API documentation from this {language} code in {doc_format} format.

Code containing API definitions:
{arguments['code']}

Documentation requirements:
- Format: {doc_format}
- {examples_instruction}
- Include all endpoints, parameters, and return types
- Document error responses and status codes
- Add authentication/authorization requirements where applicable
- Include rate limiting and usage guidelines
- Provide clear parameter descriptions and constraints

Generate production-ready API documentation that developers can use immediately."""

            log_info(f"Generating API documentation in {doc_format} format")
            documentation = await call_vllm_api(prompt, "documentation")

            log_info(f"Generated {len(documentation)} characters of API documentation")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=documentation)]

        elif name == "generate_integration_tests":
            test_scenarios = arguments.get(
                "test_scenarios",
                ["happy_path", "error_cases", "edge_cases", "authentication"],
            )
            framework = arguments.get("framework", "pytest")
            include_fixtures = arguments.get("include_fixtures", True)
            language = arguments.get("language", "python")

            scenarios_list = ", ".join(test_scenarios)
            fixtures_instruction = (
                "Include comprehensive test fixtures and mock data"
                if include_fixtures
                else "Generate tests without fixtures"
            )

            prompt = f"""Generate comprehensive integration tests for this {language} code using {framework}.

Code to test:
{arguments['code']}

Test scenarios to cover: {scenarios_list}
{fixtures_instruction}

Generate integration tests that include:
1. Complete test setup and teardown
2. Database/external service integration testing
3. API endpoint integration tests
4. Authentication and authorization testing
5. Error handling and edge case validation
6. Performance and load considerations
7. Data validation and integrity checks

Provide runnable, production-ready integration tests with proper test isolation and cleanup."""

            log_info(f"Generating integration tests using {framework}")
            tests = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(tests)} characters of integration tests")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=tests)]

        elif name == "security_scan_code":
            vulnerability_types = arguments.get(
                "vulnerability_types",
                [
                    "injection",
                    "authentication",
                    "authorization",
                    "crypto",
                    "input_validation",
                ],
            )
            language = arguments.get("language", "python")
            include_fixes = arguments.get("include_fixes", True)
            severity_threshold = arguments.get("severity_threshold", "medium")

            vuln_types = ", ".join(vulnerability_types)
            fixes_instruction = (
                "Include specific fix recommendations with code examples"
                if include_fixes
                else "Only identify vulnerabilities without fixes"
            )

            prompt = f"""Perform a comprehensive security analysis of this {language} code.

Code to scan:
{arguments['code']}

Vulnerability types to check: {vuln_types}
Minimum severity: {severity_threshold}
{fixes_instruction}

Provide a detailed security assessment with:
1. Identified vulnerabilities with severity ratings (CRITICAL/HIGH/MEDIUM/LOW)
2. Specific code locations and vulnerable patterns
3. Potential attack vectors and exploitation scenarios
4. OWASP classification where applicable
5. Remediation steps with secure code examples
6. Best practice recommendations for similar code
7. Prevention strategies for future development

Focus on practical, actionable security improvements that can be implemented immediately."""

            log_info("Performing security scan")
            security_analysis = await call_vllm_api(prompt, "analysis")

            log_info(
                f"Generated {len(security_analysis)} characters of security analysis"
            )
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=security_analysis)]

        elif name == "generate_unit_test_fixtures":
            fixture_types = arguments.get(
                "fixture_types",
                ["mock_data", "test_objects", "api_responses", "database_records"],
            )
            framework = arguments.get("framework", "pytest")
            data_realism = arguments.get("data_realism", "realistic")

            fixture_list = ", ".join(fixture_types)

            prompt = f"""Generate comprehensive test fixtures for unit testing this code using {framework}.

Code under test:
{arguments['code_under_test']}

Fixture types needed: {fixture_list}
Data realism level: {data_realism}

Generate test fixtures that include:
1. Mock data objects with realistic values
2. Test class instances with proper initialization
3. API response mocks with various scenarios
4. Database record fixtures with relationships
5. Configuration and setup fixtures
6. Error case fixtures for negative testing
7. Parameterized test data sets

Ensure fixtures are:
- Reusable across multiple tests
- Easy to maintain and modify
- Realistic enough for meaningful testing
- Isolated and independent
- Well-documented with clear usage examples

Provide complete, runnable fixture code with proper {framework} decorators and conventions."""

            log_info(f"Generating test fixtures using {framework}")
            fixtures = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(fixtures)} characters of test fixtures")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=fixtures)]

        elif name == "add_type_annotations":
            annotation_style = arguments.get("annotation_style", "comprehensive")
            language = arguments.get("language", "python")
            include_generics = arguments.get("include_generics", True)

            generics_instruction = (
                "Include generic type parameters where appropriate"
                if include_generics
                else "Use basic types without generics"
            )

            prompt = f"""Add comprehensive type annotations to this {language} code.

Code to annotate:
{arguments['code']}

Annotation style: {annotation_style}
{generics_instruction}

Add type hints for:
1. Function parameters and return types
2. Variable assignments where helpful
3. Class attributes and methods
4. Generic types and type variables where applicable
5. Union types for multiple possible types
6. Optional types for nullable values
7. Complex types (Dict, List, Tuple with specific types)

Ensure type annotations are:
- Accurate and helpful for static analysis
- Compatible with modern {language} type checking
- Consistent throughout the codebase
- Not overly verbose or redundant
- Following current best practices

Return the complete code with all appropriate type annotations added."""

            log_info(f"Adding type annotations in {annotation_style} style")
            annotated_code = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(annotated_code)} characters of annotated code")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=annotated_code)]

        elif name == "optimize_imports":
            optimization_types = arguments.get(
                "optimization_types", ["remove_unused", "sort", "group", "add_missing"]
            )
            language = arguments.get("language", "python")
            style_guide = arguments.get("style_guide", "pep8")

            optimizations = ", ".join(optimization_types)

            prompt = f"""Optimize the import statements in this {language} code following {style_guide} style guidelines.

Code with imports to optimize:
{arguments['code']}

Optimizations to perform: {optimizations}

Import optimization tasks:
1. Remove unused imports (analyze actual usage)
2. Sort imports alphabetically within groups
3. Group imports properly (standard library, third-party, local)
4. Add missing imports for referenced but unimported modules
5. Consolidate multiple imports from same module
6. Fix import order according to {style_guide} standards
7. Remove duplicate imports
8. Optimize relative vs absolute imports

Ensure the optimized imports:
- Follow {style_guide} conventions exactly
- Maintain all necessary functionality
- Are properly grouped and sorted
- Include all required imports without extras
- Use consistent import styles throughout

Return the complete code with optimized import statements."""

            log_info(f"Optimizing imports following {style_guide} guidelines")
            optimized_code = await call_vllm_api(prompt, "code_generation")

            log_info(f"Generated {len(optimized_code)} characters of optimized code")
            metrics_collector.record_execution(name, start_time, True)
            return [TextContent(type="text", text=optimized_code)]
        # Unknown tool
        log_error(f"Unknown tool: {name}")
        metrics_collector.record_execution(
            name, start_time, False, error_type="unknown_tool"
        )
        return create_error_response(name, f"Unknown tool: {name}")

    except Exception as e:
        log_error(f"Error in call_tool({name}): {e}", exc_info=True)
        metrics_collector.record_execution(
            name, start_time, False, error_type=type(e).__name__
        )
        return create_error_response(name, str(e))


# ========== MAIN ENTRY POINT ==========
async def main():
    from mcp.server.stdio import stdio_server

    try:
        log_info("Initializing Enhanced MCP server...")

        # Test vLLM connection
        log_info("Testing vLLM connection...")
        try:
            client = await vllm_client.get_client()
            response = await client.get(
                CONFIG.vllm.api_url.replace("/chat/completions", "/models")
            )
            log_info(f"✓ vLLM connection OK: {response.status_code}")
            log_debug(f"vLLM models response: {response.text}")
        except Exception as e:
            log_error(f"⚠ Cannot connect to vLLM: {e}")
            log_error(
                "Server will start anyway, but tools will fail until vLLM is available"
            )

        log_info("Starting stdio server...")
        async with stdio_server() as (read_stream, write_stream):
            log_info("✓ Enhanced MCP server ready and listening")
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    except KeyboardInterrupt:
        log_info("Server stopped by user")
    except Exception as e:
        log_error(f"FATAL ERROR in main(): {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        await vllm_client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_info("Shutting down...")
    except Exception as e:
        log_error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
