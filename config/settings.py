"""
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
                    k: (
                        type(getattr(Config, k)).__call__(**v)
                        if isinstance(v, dict)
                        else v
                    )
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
