#!/usr/bin/env python3
"""
Create configuration module files
"""

import os
from pathlib import Path


def create_config_files():
    """Create all configuration-related files"""

    base_dir = Path("mcp-vllm-delegator")
    config_dir = base_dir / "config"

    # Ensure directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    # config/settings.py
    settings_content = '''"""
Configuration management for the vLLM MCP Delegator
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml


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
    allowed_paths: Optional[List[str]] = None
    max_file_size: int = 1024 * 1024  # 1MB
    max_response_length: int = 50000
    allowed_commands: Optional[Dict[str, List[str]]] = None

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
    file: str = "./logs/vllm_mcp_delegator.log"


@dataclass
class FeaturesConfig:
    caching: bool = True
    metrics: bool = True
    auto_backup: bool = True
    batch_operations: bool = True


@dataclass
class Config:
    vllm: Optional[VLLMConfig] = None
    security: Optional[SecurityConfig] = None
    logging: Optional[LoggingConfig] = None
    features: Optional[FeaturesConfig] = None

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
            file=os.getenv("LOG_FILE", "./logs/vllm_mcp_delegator.log"),
        ),
    )
'''

    # config/models.py
    models_content = '''"""
Model configurations and language detection utilities
"""

import os
from pathlib import Path
from typing import Dict

# Model configurations for different task types
MODEL_CONFIGS = {
    "code_generation": {"temperature": 0.2, "max_tokens": 2000},
    "documentation": {"temperature": 0.3, "max_tokens": 1500},
    "analysis": {"temperature": 0.1, "max_tokens": 1000},
    "git_commit": {"temperature": 0.3, "max_tokens": 200},
    "explanation": {"temperature": 0.3, "max_tokens": 800},
}

# Language configurations for project detection
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


def get_model_config(task_type: str, vllm_config=None) -> dict:
    """Get model configuration for specific task type"""
    config = MODEL_CONFIGS.get(task_type, MODEL_CONFIGS["code_generation"])
    model_name = vllm_config.model if vllm_config else "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
    return {"model": model_name, **config}


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


def detect_language_from_code(code: str, filename: str = "") -> str:
    """Auto-detect programming language from code content or filename"""
    # Check filename extension first
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".php": "php",
            ".rb": "ruby",
        }
        if ext in ext_map:
            return ext_map[ext]

    # Analyze code content for language hints
    code_lower = code.lower()

    # Python indicators
    if any(keyword in code_lower for keyword in ["def ", "import ", "from ", "class ", "__init__", "elif"]):
        return "python"

    # JavaScript/TypeScript indicators
    if any(keyword in code_lower for keyword in ["function", "const ", "let ", "var ", "=>", "console.log"]):
        if "interface " in code_lower or ": string" in code_lower or ": number" in code_lower:
            return "typescript"
        return "javascript"

    # Default fallback
    return "python"
'''

    # Write files
    files = {
        "settings.py": settings_content,
        "models.py": models_content,
    }

    for filename, content in files.items():
        file_path = config_dir / filename
        file_path.write_text(content)
        print(f"Created: {file_path}")

    print("Configuration files created successfully!")


if __name__ == "__main__":
    create_config_files()
