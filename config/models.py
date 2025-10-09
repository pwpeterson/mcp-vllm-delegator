"""
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
    model_name = (
        vllm_config.model if vllm_config else "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
    )
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
    if any(
        keyword in code_lower
        for keyword in ["def ", "import ", "from ", "class ", "__init__", "elif"]
    ):
        return "python"

    # JavaScript/TypeScript indicators
    if any(
        keyword in code_lower
        for keyword in ["function", "const ", "let ", "var ", "=>", "console.log"]
    ):
        if (
            "interface " in code_lower
            or ": string" in code_lower
            or ": number" in code_lower
        ):
            return "typescript"
        return "javascript"

    # Default fallback
    return "python"
