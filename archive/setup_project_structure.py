#!/usr/bin/env python3
"""
Setup script to create the modular directory structure for mcp-vllm-delegator
"""

import os
from pathlib import Path


def create_directory_structure():
    """Create the complete directory structure for the modular MCP server"""

    # Base directory
    base_dir = Path("mcp-vllm-delegator")

    # Directory structure
    directories = [
        "config",
        "core",
        "security",
        "tools",
        "utils",
        "logs",  # For log files
        "tests",  # For future tests
    ]

    # Create base directory
    base_dir.mkdir(exist_ok=True)
    print(f"Created base directory: {base_dir}")

    # Create subdirectories
    for directory in directories:
        dir_path = base_dir / directory
        dir_path.mkdir(exist_ok=True)
        print(f"Created directory: {dir_path}")

        # Create __init__.py files for Python packages
        init_file = dir_path / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# This file makes the directory a Python package\n")
            print(f"Created __init__.py: {init_file}")

    # Create additional files
    additional_files = {
        "requirements.txt": """# Core dependencies
mcp>=1.0.0
httpx>=0.25.0
pyyaml>=6.0.0

# Optional dependencies for enhanced features
pytest>=7.0.0  # For testing
black>=23.0.0  # For code formatting
isort>=5.0.0   # For import sorting
""",
        "README.md": """# MCP vLLM Delegator

A modular Model Context Protocol (MCP) server that delegates coding tasks to a local vLLM instance.

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python main.py
```

## Configuration

Set environment variables or create a `config.yaml` file:

- `VLLM_API_URL`: URL of your vLLM server (default: http://localhost:8002/v1/chat/completions)
- `VLLM_MODEL`: Model name (default: Qwen/Qwen2.5-Coder-32B-Instruct-AWQ)
- `LOGGING_ON`: Enable logging (default: true)
- `LOG_LEVEL`: Logging level (default: INFO)

## Features

- Code generation and completion
- Pre-commit validation and auto-correction
- Git workflow automation
- Code analysis and refactoring suggestions
- Documentation generation
- Project scaffolding
""",
        "config.yaml.example": """# Example configuration file
vllm:
  api_url: "http://localhost:8002/v1/chat/completions"
  model: "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
  timeout: 180
  max_retries: 3

security:
  max_file_size: 1048576  # 1MB
  max_response_length: 50000
  allowed_paths:
    - "."

logging:
  enabled: true
  level: "INFO"
  file: "./logs/delegator.log"

features:
  caching: true
  metrics: true
  auto_backup: true
""",
        ".gitignore": """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
.venv/
env/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# Config files with secrets
config.yaml
.env.local

# Backup files
*.backup.*

# OS
.DS_Store
Thumbs.db
""",
    }

    # Create additional files
    for filename, content in additional_files.items():
        file_path = base_dir / filename
        if not file_path.exists():
            file_path.write_text(content)
            print(f"Created file: {file_path}")

    print(f"\nDirectory structure created successfully in: {base_dir.absolute()}")
    print("\nNext steps:")
    print("1. Run the individual file creation scripts")
    print("2. Review and modify config.yaml.example as needed")
    print("3. Install dependencies: pip install -r requirements.txt")


if __name__ == "__main__":
    create_directory_structure()
