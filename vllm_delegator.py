# mcp_vllm_delegator.py
import asyncio
import json
import sys
import logging
import os
import subprocess
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
import httpx

# ========== CONFIGURABLE LOGGING SETUP ==========
LOGGING_ENABLED = os.getenv('LOGGING_ON', 'false').lower() in ('true', '1', 'yes', 'on')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.getenv('LOG_FILE', '/tmp/vllm_mcp_delegator.log')

if LOGGING_ENABLED:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stderr)
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("vLLM MCP Delegator Starting (Logging ENABLED)")
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info(f"Log File: {LOG_FILE}")
    logger.info("=" * 50)
else:
    logging.basicConfig(
        level=logging.ERROR,
        format='%(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]
    )
    logger = logging.getLogger(__name__)

def log_info(msg):
    if LOGGING_ENABLED:
        logger.info(msg)

def log_debug(msg):
    if LOGGING_ENABLED:
        logger.debug(msg)

def log_error(msg, exc_info=False):
    logger.error(msg, exc_info=exc_info)

# Configuration
VLLM_API_URL = "http://localhost:8002/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"

log_info(f"vLLM API URL: {VLLM_API_URL}")
log_info(f"vLLM Model: {VLLM_MODEL}")

server = Server("vllm-delegator")

# Helper function to validate and normalize paths
def safe_path(base_path: str, target_path: str) -> str:
    """Validate that target_path is within base_path to prevent directory traversal"""
    base = Path(base_path).resolve()
    target = (base / target_path).resolve()
    
    if not target.is_relative_to(base):
        raise ValueError(f"Path {target_path} is outside allowed directory")
    
    return str(target)
@server.list_tools()
async def list_tools() -> list[Tool]:
    log_info("list_tools() called")
    tools = [
        Tool(
            name="generate_simple_code",
            description="Delegate simple, straightforward code generation to local Qwen2.5-Coder LLM. Use for: boilerplate code, basic CRUD functions, simple utility functions, standard implementations, repetitive code patterns. NOT for: complex algorithms, architectural decisions, code requiring deep context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Clear, specific prompt for code generation"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language (e.g., python, javascript, rust)",
                        "default": "python"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate",
                        "default": 1000
                    }
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="complete_code",
            description="Complete or extend existing code using local LLM. Good for: filling in function bodies, completing class methods, adding docstrings, implementing obvious next steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_context": {
                        "type": "string",
                        "description": "Existing code that needs completion"
                    },
                    "instruction": {
                        "type": "string",
                        "description": "What to complete or add"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate",
                        "default": 800
                    }
                },
                "required": ["code_context", "instruction"]
            }
        ),
        Tool(
            name="explain_code",
            description="Get quick code explanations from local LLM for simple code snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to explain"
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": ["brief", "detailed"],
                        "default": "brief"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="generate_docstrings",
            description="Generate docstrings/comments for code using local LLM. Use for: function/class documentation, inline comments for simple logic. Supports multiple documentation styles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code that needs documentation"
                    },
                    "style": {
                        "type": "string",
                        "enum": ["google", "numpy", "sphinx", "jsdoc", "rustdoc"],
                        "default": "google",
                        "description": "Documentation style to use"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="generate_tests",
            description="Generate basic unit tests using local LLM. Use for: simple function tests, basic edge cases, happy path tests. NOT for: integration tests, complex mocking scenarios.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to generate tests for"
                    },
                    "test_framework": {
                        "type": "string",
                        "enum": ["pytest", "unittest", "jest", "mocha", "vitest", "cargo-test"],
                        "default": "pytest",
                        "description": "Testing framework to use"
                    },
                    "coverage_level": {
                        "type": "string",
                        "enum": ["basic", "standard", "comprehensive"],
                        "default": "standard",
                        "description": "basic=happy path, standard=+edge cases, comprehensive=+error cases"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="refactor_simple_code",
            description="Refactor simple code patterns using local LLM. Use for: variable renaming, extract method, simplify conditionals, remove duplication in straightforward code. NOT for: complex architectural refactoring, cross-file changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to refactor"
                    },
                    "refactor_type": {
                        "type": "string",
                        "description": "Type of refactoring (e.g., 'extract method', 'rename variables', 'simplify conditionals', 'remove duplication')"
                    },
                    "additional_context": {
                        "type": "string",
                        "description": "Additional context or constraints for refactoring",
                        "default": ""
                    }
                },
                "required": ["code", "refactor_type"]
            }
        ),
        Tool(
            name="fix_simple_bugs",
            description="Fix straightforward bugs using local LLM. Use for: syntax errors, simple logic errors, obvious type mismatches, missing imports for standard libraries. NOT for: race conditions, memory leaks, complex logic errors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code containing the bug"
                    },
                    "error_message": {
                        "type": "string",
                        "description": "Error message or bug description"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about the bug",
                        "default": ""
                    }
                },
                "required": ["code", "error_message"]
            }
        ),
        Tool(
            name="convert_code_format",
            description="Convert between code formats/styles using local LLM. Use for: camelCase to snake_case, JSON to YAML, SQL to ORM, callback to async/await (simple cases).",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to convert"
                    },
                    "from_format": {
                        "type": "string",
                        "description": "Current format (e.g., 'camelCase', 'json', 'callbacks', 'sql')"
                    },
                    "to_format": {
                        "type": "string",
                        "description": "Target format (e.g., 'snake_case', 'yaml', 'async/await', 'orm')"
                    }
                },
                "required": ["code", "from_format", "to_format"]
            }
        ),
        Tool(
            name="generate_boilerplate_file",
            description="Generate complete boilerplate files using local LLM. Use for: REST API routes, database models, config files, Dockerfiles, GitHub Actions workflows, basic CLI scripts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_type": {
                        "type": "string",
                        "description": "Type of file to generate (e.g., 'rest_api_route', 'database_model', 'dockerfile', 'github_action', 'cli_script')"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language or config format",
                        "default": "python"
                    },
                    "options": {
                        "type": "object",
                        "description": "Additional options as key-value pairs (e.g., framework, database_type, authentication)",
                        "default": {}
                    }
                },
                "required": ["file_type", "language"]
            }
        ),
        Tool(
            name="improve_code_style",
            description="Improve code style/readability using local LLM. Use for: consistent naming, line length, import ordering, simple readability improvements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to improve"
                    },
                    "style_guide": {
                        "type": "string",
                        "enum": ["pep8", "black", "airbnb", "google", "standard", "prettier"],
                        "default": "pep8",
                        "description": "Style guide to follow"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="generate_schema",
            description="Generate data schemas/models using local LLM. Schema types: pydantic, sqlalchemy, json_schema, graphql, typescript_interface, protobuf. Use for: straightforward data models with standard field types.",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of the data structure to generate"
                    },
                    "schema_type": {
                        "type": "string",
                        "enum": ["pydantic", "sqlalchemy", "json_schema", "graphql", "typescript_interface", "protobuf"],
                        "description": "Type of schema to generate"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python"
                    }
                },
                "required": ["description", "schema_type"]
            }
        ),
        Tool(
            name="generate_git_commit_message",
            description="Generate conventional commit messages using local LLM. Use for: creating clear, descriptive commit messages following conventional commit format.",
            inputSchema={
                "type": "object",
                "properties": {
                    "changes_summary": {
                        "type": "string",
                        "description": "Summary of changes made (can be git diff output or description)"
                    },
                    "commit_type": {
                        "type": "string",
                        "enum": ["feat", "fix", "docs", "style", "refactor", "test", "chore", "auto"],
                        "default": "auto",
                        "description": "Type of commit (auto = let LLM decide)"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Optional scope of the change (e.g., 'api', 'ui', 'auth')",
                        "default": ""
                    }
                },
                "required": ["changes_summary"]
            }
        ),
        Tool(
            name="generate_gitignore",
            description="Generate .gitignore files using local LLM. Use for: creating comprehensive .gitignore files for specific languages/frameworks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Primary programming language (e.g., python, javascript, rust, go)"
                    },
                    "frameworks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional frameworks/tools (e.g., ['react', 'docker', 'vscode'])",
                        "default": []
                    },
                    "custom_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Custom patterns to include",
                        "default": []
                    }
                },
                "required": ["language"]
            }
        ),
        Tool(
            name="generate_github_workflow",
            description="Generate GitHub Actions workflow files using local LLM. Use for: CI/CD pipelines, automated testing, deployment workflows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_type": {
                        "type": "string",
                        "enum": ["ci", "cd", "test", "release", "lint", "security", "custom"],
                        "description": "Type of workflow to generate"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python"
                    },
                    "triggers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Workflow triggers (e.g., ['push', 'pull_request', 'schedule'])",
                        "default": ["push", "pull_request"]
                    },
                    "custom_requirements": {
                        "type": "string",
                        "description": "Additional requirements or steps",
                        "default": ""
                    }
                },
                "required": ["workflow_type"]
            }
        ),
        Tool(
            name="generate_pr_description",
            description="Generate pull request descriptions using local LLM. Use for: creating comprehensive PR descriptions with context and changes summary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "changes_summary": {
                        "type": "string",
                        "description": "Summary of changes made (can be git diff output or description)"
                    },
                    "pr_type": {
                        "type": "string",
                        "enum": ["feature", "bugfix", "hotfix", "refactor", "docs", "chore"],
                        "description": "Type of pull request"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about why these changes were made",
                        "default": ""
                    },
                    "breaking_changes": {
                        "type": "boolean",
                        "description": "Whether this PR contains breaking changes",
                        "default": False
                    }
                },
                "required": ["changes_summary", "pr_type"]
            }
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
                        "default": True
                    }
                },
                "required": []
            }
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
                        "description": "Files to add (use ['.'] for all files)"
                    }
                },
                "required": ["files"]
            }
        ),
        Tool(
            name="git_commit",
            description="Execute git commit command with message. Automatically pushes to origin if successful.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Commit message"
                    },
                    "auto_push": {
                        "type": "boolean",
                        "description": "Automatically push after successful commit",
                        "default": True
                    }
                },
                "required": ["message"]
            }
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
                        "default": False
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific files to diff (optional)",
                        "default": []
                    }
                },
                "required": []
            }
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
                        "default": 10
                    },
                    "oneline": {
                        "type": "boolean",
                        "description": "Show one line per commit",
                        "default": True
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="create_config_file",
            description="Generate and create common configuration files using local LLM. Use for: .env, package.json, requirements.txt, Dockerfile, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_type": {
                        "type": "string",
                        "enum": ["env", "package_json", "requirements_txt", "dockerfile", "makefile", "gitignore", "readme", "contributing", "license", "custom"],
                        "description": "Type of config file to generate"
                    },
                    "path": {
                        "type": "string",
                        "description": "File path where to create the file"
                    },
                    "options": {
                        "type": "object",
                        "description": "Configuration options (e.g., project_name, language, dependencies)",
                        "default": {}
                    },
                    "custom_prompt": {
                        "type": "string",
                        "description": "Custom prompt for file generation (used with 'custom' file_type)",
                        "default": ""
                    }
                },
                "required": ["file_type", "path"]
            }
        ),
        Tool(
            name="create_directory_structure",
            description="Generate and create standard directory structures using local LLM. Use for: project scaffolding, standard layouts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "structure_type": {
                        "type": "string",
                        "enum": ["python_project", "node_project", "rust_project", "go_project", "web_project", "api_project", "custom"],
                        "description": "Type of directory structure to create"
                    },
                    "base_path": {
                        "type": "string",
                        "description": "Base directory path"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project name"
                    },
                    "options": {
                        "type": "object",
                        "description": "Additional options (e.g., include_tests, include_docs)",
                        "default": {}
                    }
                },
                "required": ["structure_type", "base_path", "project_name"]
            }
        ),
        Tool(
            name="create_github_issue",
            description="Generate and create GitHub issues using local LLM. Use for: bug reports, feature requests, task issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "Repository in format 'owner/repo'"
                    },
                    "issue_type": {
                        "type": "string",
                        "enum": ["bug", "feature", "enhancement", "task", "question", "documentation"],
                        "description": "Type of issue"
                    },
                    "title": {
                        "type": "string",
                        "description": "Issue title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Issue description or context"
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to apply",
                        "default": []
                    }
                },
                "required": ["repository", "issue_type", "title", "description"]
            }
        ),
        Tool(
            name="create_github_pr",
            description="Generate and create GitHub pull requests using local LLM. Use for: feature PRs, bug fixes, documentation updates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "Repository in format 'owner/repo'"
                    },
                    "head_branch": {
                        "type": "string",
                        "description": "Source branch"
                    },
                    "base_branch": {
                        "type": "string",
                        "description": "Target branch",
                        "default": "main"
                    },
                    "title": {
                        "type": "string",
                        "description": "PR title"
                    },
                    "changes_summary": {
                        "type": "string",
                        "description": "Summary of changes made"
                    },
                    "pr_type": {
                        "type": "string",
                        "enum": ["feature", "bugfix", "hotfix", "refactor", "docs", "chore"],
                        "description": "Type of pull request"
                    }
                },
                "required": ["repository", "head_branch", "title", "changes_summary", "pr_type"]
            }
        ),
        Tool(
            name="execute_dev_command",
            description="Execute common development commands using subprocess. Use for: package installation, build commands, test execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_type": {
                        "type": "string",
                        "enum": ["npm_install", "pip_install", "cargo_build", "go_mod_tidy", "make", "test", "custom"],
                        "description": "Type of command to execute"
                    },
                    "arguments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command arguments",
                        "default": []
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for command execution",
                        "default": "."
                    },
                    "custom_command": {
                        "type": "string",
                        "description": "Custom command to execute (used with 'custom' command_type)",
                        "default": ""
                    }
                },
                "required": ["command_type"]
            }
        ),
        Tool(
            name="create_database_schema",
            description="Generate and execute SQLite database schema creation using local LLM. Use for: table creation, index creation, basic schema setup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_path": {
                        "type": "string",
                        "description": "Path to SQLite database file"
                    },
                    "schema_description": {
                        "type": "string",
                        "description": "Description of the schema to create"
                    },
                    "tables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        },
                        "description": "Table specifications",
                        "default": []
                    }
                },
                "required": ["database_path", "schema_description"]
            }
        ),
        Tool(
            name="generate_sql_queries",
            description="Generate common SQL queries using local LLM. Use for: CRUD operations, data analysis queries, reporting queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["select", "insert", "update", "delete", "create_table", "create_index", "analytics"],
                        "description": "Type of SQL query to generate"
                    },
                    "table_info": {
                        "type": "string",
                        "description": "Information about tables and columns involved"
                    },
                    "requirements": {
                        "type": "string",
                        "description": "Specific requirements for the query"
                    },
                    "execute": {
                        "type": "boolean",
                        "description": "Whether to execute the query (for safe operations only)",
                        "default": False
                    },
                    "database_path": {
                        "type": "string",
                        "description": "Database path (required if execute=true)",
                        "default": ""
                    }
                },
                "required": ["query_type", "table_info", "requirements"]
            }
        )
    ]
    log_info(f"Returning {len(tools)} tools")
    return tools

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    log_info(f"call_tool() invoked: {name}")
    log_debug(f"Arguments: {json.dumps(arguments, indent=2)}")
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            
            if name == "generate_simple_code":
                prompt = f"""You are a code generator. Generate clean, working {arguments.get('language', 'python')} code for the following request.
Only output the code, no explanations unless asked.

Request: {arguments['prompt']}"""
                
                log_info("Calling vLLM API for generate_simple_code")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": arguments.get('max_tokens', 1000),
                    "temperature": 0.2
                })
                
                result = response.json()
                code = result['choices'][0]['message']['content']
                log_info(f"Generated {len(code)} characters of code")
                return [TextContent(type="text", text=code)]
            
            elif name == "complete_code":
                prompt = f"""Complete the following code according to the instruction.

Code:
{arguments['code_context']}

Instruction: {arguments['instruction']}

Provide only the completion, maintaining the existing code style."""
                
                log_info("Calling vLLM API for complete_code")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": arguments.get('max_tokens', 800),
                    "temperature": 0.2
                })
                
                result = response.json()
                completion = result['choices'][0]['message']['content']
                log_info(f"Generated {len(completion)} characters of completion")
                return [TextContent(type="text", text=completion)]
            
            elif name == "explain_code":
                detail = "briefly" if arguments.get('detail_level') == 'brief' else "in detail"
                prompt = f"""Explain {detail} what this code does:

{arguments['code']}"""
                
                log_info("Calling vLLM API for explain_code")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3
                })
                
                result = response.json()
                explanation = result['choices'][0]['message']['content']
                log_info(f"Generated {len(explanation)} characters of explanation")
                return [TextContent(type="text", text=explanation)]
            
            elif name == "generate_docstrings":
                style = arguments.get('style', 'google')
                language = arguments.get('language', 'python')
                prompt = f"""Add {style}-style docstrings to this {language} code. Return the complete code with docstrings added.

{arguments['code']}"""
                
                log_info("Calling vLLM API for generate_docstrings")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.2
                })
                
                result = response.json()
                documented_code = result['choices'][0]['message']['content']
                log_info(f"Generated {len(documented_code)} characters of documented code")
                return [TextContent(type="text", text=documented_code)]
            
            elif name == "generate_tests":
                framework = arguments.get('test_framework', 'pytest')
                coverage = arguments.get('coverage_level', 'standard')
                
                coverage_desc = {
                    'basic': 'basic happy path tests',
                    'standard': 'happy path tests plus common edge cases',
                    'comprehensive': 'comprehensive tests including happy path, edge cases, and error conditions'
                }
                
                prompt = f"""Generate {coverage_desc[coverage]} using {framework} for the following code.

Code to test:
{arguments['code']}

Generate complete, runnable test code."""
                
                log_info("Calling vLLM API for generate_tests")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.2
                })
                
                result = response.json()
                tests = result['choices'][0]['message']['content']
                log_info(f"Generated {len(tests)} characters of tests")
                return [TextContent(type="text", text=tests)]
            
            elif name == "refactor_simple_code":
                context = arguments.get('additional_context', '')
                context_str = f"\n\nAdditional context: {context}" if context else ""
                
                prompt = f"""Refactor the following code using this refactoring pattern: {arguments['refactor_type']}
{context_str}

Original code:
{arguments['code']}

Provide the refactored code, maintaining functionality."""
                
                log_info("Calling vLLM API for refactor_simple_code")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.2
                })
                
                result = response.json()
                refactored = result['choices'][0]['message']['content']
                log_info(f"Generated {len(refactored)} characters of refactored code")
                return [TextContent(type="text", text=refactored)]
            
            elif name == "fix_simple_bugs":
                context = arguments.get('context', '')
                context_str = f"\n\nAdditional context: {context}" if context else ""
                
                prompt = f"""Fix the bug in this code.

Error message: {arguments['error_message']}
{context_str}

Code with bug:
{arguments['code']}

Provide the corrected code with a brief explanation of the fix."""
                
                log_info("Calling vLLM API for fix_simple_bugs")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.2
                })
                
                result = response.json()
                fixed_code = result['choices'][0]['message']['content']
                log_info(f"Generated {len(fixed_code)} characters of fixed code")
                return [TextContent(type="text", text=fixed_code)]
            
            elif name == "convert_code_format":
                prompt = f"""Convert this code from {arguments['from_format']} to {arguments['to_format']}.

Original code:
{arguments['code']}

Provide only the converted code."""
                
                log_info("Calling vLLM API for convert_code_format")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.2
                })
                
                result = response.json()
                converted = result['choices'][0]['message']['content']
                log_info(f"Generated {len(converted)} characters of converted code")
                return [TextContent(type="text", text=converted)]
            
            elif name == "generate_boilerplate_file":
                options_str = json.dumps(arguments.get('options', {}), indent=2)
                
                prompt = f"""Generate a complete {arguments['file_type']} file in {arguments['language']}.

Options: {options_str}

Generate production-ready, well-structured boilerplate code."""
                
                log_info("Calling vLLM API for generate_boilerplate_file")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.2
                })
                
                result = response.json()
                boilerplate = result['choices'][0]['message']['content']
                log_info(f"Generated {len(boilerplate)} characters of boilerplate")
                return [TextContent(type="text", text=boilerplate)]
            
            elif name == "improve_code_style":
                style_guide = arguments.get('style_guide', 'pep8')
                language = arguments.get('language', 'python')
                
                prompt = f"""Improve the code style following {style_guide} guidelines for {language}.
Focus on: naming conventions, formatting, readability, and best practices.

Original code:
{arguments['code']}

Provide the improved code."""
                
                log_info("Calling vLLM API for improve_code_style")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.2
                })
                
                result = response.json()
                improved = result['choices'][0]['message']['content']
                log_info(f"Generated {len(improved)} characters of improved code")
                return [TextContent(type="text", text=improved)]
            
            elif name == "generate_schema":
                language = arguments.get('language', 'python')
                
                prompt = f"""Generate a {arguments['schema_type']} schema in {language} based on this description:

{arguments['description']}

Generate complete, well-typed schema code."""
                
                log_info("Calling vLLM API for generate_schema")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.2
                })
                
                result = response.json()
                schema = result['choices'][0]['message']['content']
                log_info(f"Generated {len(schema)} characters of schema")
                return [TextContent(type="text", text=schema)]
            
            elif name == "generate_git_commit_message":
                commit_type = arguments.get('commit_type', 'auto')
                scope = arguments.get('scope', '')
                
                type_instruction = f"Use commit type '{commit_type}'" if commit_type != 'auto' else "Choose appropriate commit type (feat, fix, docs, style, refactor, test, chore)"
                scope_instruction = f" with scope '{scope}'" if scope else ""
                
                prompt = f"""Generate a conventional commit message for these changes.

{type_instruction}{scope_instruction}.

Changes summary:
{arguments['changes_summary']}

Format: type(scope): description

Provide only the commit message, no explanations."""
                
                log_info("Calling vLLM API for generate_git_commit_message")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.3
                })
                
                result = response.json()
                commit_message = result['choices'][0]['message']['content'].strip()
                log_info(f"Generated commit message: {commit_message[:50]}...")
                return [TextContent(type="text", text=commit_message)]
            
            elif name == "generate_gitignore":
                frameworks = arguments.get('frameworks', [])
                custom_patterns = arguments.get('custom_patterns', [])
                
                frameworks_str = ", ".join(frameworks) if frameworks else "none"
                custom_str = "\n".join(custom_patterns) if custom_patterns else "none"
                
                prompt = f"""Generate a comprehensive .gitignore file for {arguments['language']}.

Additional frameworks/tools: {frameworks_str}
Custom patterns to include: {custom_str}

Include common patterns for the language, IDE files, OS files, and build artifacts.
Provide only the .gitignore content, no explanations."""
                
                log_info("Calling vLLM API for generate_gitignore")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.2
                })
                
                result = response.json()
                gitignore = result['choices'][0]['message']['content']
                log_info(f"Generated {len(gitignore)} characters of .gitignore")
                return [TextContent(type="text", text=gitignore)]
            
            elif name == "generate_github_workflow":
                language = arguments.get('language', 'python')
                triggers = arguments.get('triggers', ['push', 'pull_request'])
                custom_requirements = arguments.get('custom_requirements', '')
                
                triggers_str = ", ".join(triggers)
                custom_str = f"\n\nAdditional requirements: {custom_requirements}" if custom_requirements else ""
                
                prompt = f"""Generate a GitHub Actions workflow file for {arguments['workflow_type']} in {language}.

Triggers: {triggers_str}{custom_str}

Generate a complete, production-ready .github/workflows/[name].yml file.
Include appropriate steps for the workflow type and language.
Provide only the YAML content, no explanations."""
                
                log_info("Calling vLLM API for generate_github_workflow")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.2
                })
                
                result = response.json()
                workflow = result['choices'][0]['message']['content']
                log_info(f"Generated {len(workflow)} characters of workflow")
                return [TextContent(type="text", text=workflow)]
            
            elif name == "generate_pr_description":
                context = arguments.get('context', '')
                breaking_changes = arguments.get('breaking_changes', False)
                
                context_str = f"\n\nContext: {context}" if context else ""
                breaking_str = "\n\n⚠️ This PR contains BREAKING CHANGES" if breaking_changes else ""
                
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
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.3
                })
                
                result = response.json()
                pr_description = result['choices'][0]['message']['content']
                log_info(f"Generated {len(pr_description)} characters of PR description")
                return [TextContent(type="text", text=pr_description)]
            
            elif name == "git_status":
                porcelain = arguments.get('porcelain', True)
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
                        lines = output.split('\n')
                        branch_line = lines[0] if lines else ""
                        file_lines = lines[1:] if len(lines) > 1 else []
                        
                        files = {
                            "modified": [],
                            "added": [],
                            "deleted": [],
                            "untracked": []
                        }
                        
                        for line in file_lines:
                            if not line.strip():
                                continue
                            status = line[:2]
                            filename = line[3:]
                            
                            if status.startswith('M'):
                                files["modified"].append(filename)
                            elif status.startswith('A'):
                                files["added"].append(filename)
                            elif status.startswith('D'):
                                files["deleted"].append(filename)
                            elif status.startswith('??'):
                                files["untracked"].append(filename)
                        
                        response_data = {
                            "ok": True,
                            "output": output,
                            "branch": branch_line,
                            "files": files,
                            "cmd": ' '.join(cmd)
                        }
                        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
                    else:
                        return [TextContent(type="text", text=output)]
                        
                except subprocess.CalledProcessError as e:
                    error_msg = f"Git status failed: {e.stderr}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            
            elif name == "git_add":
                files = arguments.get('files', [])
                if not files:
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": "No files specified"}))]
                
                cmd = ["git", "add"] + files
                log_info(f"Executing: {' '.join(cmd)}")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    log_info(f"Git add completed successfully")
                    response_data = {
                        "ok": True,
                        "output": result.stdout.strip(),
                        "cmd": ' '.join(cmd)
                    }
                    return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
                    
                except subprocess.CalledProcessError as e:
                    error_msg = f"Git add failed: {e.stderr}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            
            elif name == "git_commit":
                message = arguments.get('message', '')
                auto_push = arguments.get('auto_push', True)
                
                if not message:
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": "Commit message required"}))]
                
                cmd = ["git", "commit", "-m", message]
                log_info(f"Executing: git commit -m '[message]'")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    log_info(f"Git commit completed successfully")
                    
                    response_data = {
                        "ok": True,
                        "output": result.stdout.strip(),
                        "message": message,
                        "cmd": f"git commit -m {message}"
                    }
                    
                    # Auto-push if enabled
                    if auto_push:
                        push_cmd = ["git", "push", "origin", "HEAD"]
                        log_info("Auto-pushing to origin")
                        try:
                            push_result = subprocess.run(push_cmd, capture_output=True, text=True, check=True)
                            response_data["push"] = {
                                "ok": True,
                                "output": push_result.stdout.strip(),
                                "cmd": ' '.join(push_cmd)
                            }
                            log_info("Git push completed successfully")
                        except subprocess.CalledProcessError as e:
                            response_data["push"] = {
                                "ok": False,
                                "error": f"Push failed: {e.stderr}",
                                "cmd": ' '.join(push_cmd)
                            }
                            log_error(f"Git push failed: {e.stderr}")
                    
                    return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
                    
                except subprocess.CalledProcessError as e:
                    error_msg = f"Git commit failed: {e.stderr}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            
            elif name == "git_diff":
                staged = arguments.get('staged', False)
                files = arguments.get('files', [])
                
                cmd = ["git", "diff"]
                if staged:
                    cmd.append("--cached")
                cmd.extend(files)
                
                log_info(f"Executing: {' '.join(cmd)}")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    output = result.stdout.strip()
                    log_info(f"Git diff completed successfully")
                    return [TextContent(type="text", text=output if output else "No differences found")]
                    
                except subprocess.CalledProcessError as e:
                    error_msg = f"Git diff failed: {e.stderr}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            
            elif name == "git_log":
                limit = arguments.get('limit', 10)
                oneline = arguments.get('oneline', True)
                
                cmd = ["git", "log", f"-{limit}"]
                if oneline:
                    cmd.append("--oneline")
                
                log_info(f"Executing: {' '.join(cmd)}")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    output = result.stdout.strip()
                    log_info(f"Git log completed successfully")
                    return [TextContent(type="text", text=output if output else "No commits found")]
                    
                except subprocess.CalledProcessError as e:
                    error_msg = f"Git log failed: {e.stderr}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            
            elif name == "create_config_file":
                file_type = arguments['file_type']
                path = arguments['path']
                options = arguments.get('options', {})
                custom_prompt = arguments.get('custom_prompt', '')
                
                if file_type == 'custom' and not custom_prompt:
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": "Custom prompt required for custom file type"}))]
                
                # Generate file content using LLM
                if file_type == 'custom':
                    prompt = custom_prompt
                else:
                    options_str = json.dumps(options, indent=2) if options else "none"
                    prompt = f"""Generate a {file_type} configuration file.

Options: {options_str}

Generate complete, production-ready file content. Include comments where appropriate.
Provide only the file content, no explanations."""
                
                log_info(f"Generating {file_type} config file")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.2
                })
                
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Write file
                try:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'w') as f:
                        f.write(content)
                    
                    log_info(f"Created config file: {path}")
                    return [TextContent(type="text", text=json.dumps({
                        "ok": True,
                        "path": path,
                        "file_type": file_type,
                        "content_length": len(content)
                    }, indent=2))]
                    
                except Exception as e:
                    error_msg = f"Failed to write file {path}: {str(e)}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            
            elif name == "create_directory_structure":
                structure_type = arguments['structure_type']
                base_path = arguments['base_path']
                project_name = arguments['project_name']
                options = arguments.get('options', {})
                
                options_str = json.dumps(options, indent=2) if options else "standard options"
                
                prompt = f"""Generate a directory structure for a {structure_type} project named '{project_name}'.

Options: {options_str}

Provide a JSON list of directory paths to create (relative to base path).
Include standard directories for this project type.
Format: ["dir1", "dir2/subdir", "dir3"]

Provide only the JSON array, no explanations."""
                
                log_info(f"Generating {structure_type} directory structure")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800,
                    "temperature": 0.2
                })
                
                result = response.json()
                directories_json = result['choices'][0]['message']['content'].strip()
                
                try:
                    # Parse JSON response
                    directories = json.loads(directories_json)
                    created_dirs = []
                    
                    # Create directories
                    for dir_path in directories:
                        full_path = os.path.join(base_path, project_name, dir_path)
                        os.makedirs(full_path, exist_ok=True)
                        created_dirs.append(full_path)
                    
                    log_info(f"Created {len(created_dirs)} directories")
                    return [TextContent(type="text", text=json.dumps({
                        "ok": True,
                        "project_path": os.path.join(base_path, project_name),
                        "directories_created": created_dirs,
                        "structure_type": structure_type
                    }, indent=2))]
                    
                except (json.JSONDecodeError, Exception) as e:
                    error_msg = f"Failed to create directory structure: {str(e)}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg, "raw_response": directories_json}))]
            
            elif name == "execute_dev_command":
                command_type = arguments['command_type']
                args = arguments.get('arguments', [])
                working_dir = arguments.get('working_directory', '.')
                custom_command = arguments.get('custom_command', '')
                
                # Map command types to actual commands
                command_map = {
                    'npm_install': ['npm', 'install'] + args,
                    'pip_install': ['pip', 'install'] + args,
                    'cargo_build': ['cargo', 'build'] + args,
                    'go_mod_tidy': ['go', 'mod', 'tidy'] + args,
                    'make': ['make'] + args,
                    'test': ['npm', 'test'] + args if os.path.exists('package.json') else ['python', '-m', 'pytest'] + args
                }
                
                if command_type == 'custom':
                    if not custom_command:
                        return [TextContent(type="text", text=json.dumps({"ok": False, "error": "Custom command required"}))]
                    cmd = custom_command.split() + args
                else:
                    cmd = command_map.get(command_type)
                    if not cmd:
                        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown command type: {command_type}"}))]
                
                log_info(f"Executing: {' '.join(cmd)} in {working_dir}")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, cwd=working_dir, timeout=300)
                    
                    response_data = {
                        "ok": result.returncode == 0,
                        "command": ' '.join(cmd),
                        "working_directory": working_dir,
                        "return_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                    
                    if result.returncode != 0:
                        log_error(f"Command failed with return code {result.returncode}")
                    else:
                        log_info(f"Command executed successfully")
                    
                    return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
                    
                except subprocess.TimeoutExpired:
                    error_msg = "Command timed out after 5 minutes"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
                except Exception as e:
                    error_msg = f"Command execution failed: {str(e)}"
                    log_error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            
            elif name == "create_github_issue":
                repository = arguments['repository']
                issue_type = arguments['issue_type']
                title = arguments['title']
                description = arguments['description']
                labels = arguments.get('labels', [])
                
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
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.3
                })
                
                result = response.json()
                issue_body = result['choices'][0]['message']['content']
                
                # Note: This would normally call GitHub API, but we'll return the generated content
                # In a real implementation, you'd use the github MCP server here
                log_info(f"Generated issue content for {repository}")
                return [TextContent(type="text", text=json.dumps({
                    "ok": True,
                    "repository": repository,
                    "title": title,
                    "body": issue_body,
                    "labels": labels,
                    "issue_type": issue_type,
                    "note": "Issue content generated. Use GitHub MCP server to actually create the issue."
                }, indent=2))]
            
            elif name == "create_github_pr":
                repository = arguments['repository']
                head_branch = arguments['head_branch']
                base_branch = arguments.get('base_branch', 'main')
                title = arguments['title']
                changes_summary = arguments['changes_summary']
                pr_type = arguments['pr_type']
                
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
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.3
                })
                
                result = response.json()
                pr_body = result['choices'][0]['message']['content']
                
                # Note: This would normally call GitHub API, but we'll return the generated content
                log_info(f"Generated PR content for {repository}")
                return [TextContent(type="text", text=json.dumps({
                    "ok": True,
                    "repository": repository,
                    "title": title,
                    "body": pr_body,
                    "head_branch": head_branch,
                    "base_branch": base_branch,
                    "pr_type": pr_type,
                    "note": "PR content generated. Use GitHub MCP server to actually create the pull request."
                }, indent=2))]
            
            elif name == "create_database_schema":
                database_path = arguments['database_path']
                schema_description = arguments['schema_description']
                tables = arguments.get('tables', [])
                
                tables_info = "\n".join([f"- {table.get('name', 'unnamed')}: {table.get('description', 'no description')}" for table in tables]) if tables else "No specific tables mentioned"
                
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
                
                log_info(f"Generating database schema for {database_path}")
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.2
                })
                
                result = response.json()
                sql_schema = result['choices'][0]['message']['content']
                
                # Note: This would normally execute the SQL, but we'll return the generated schema
                # In a real implementation, you'd use the sqlite MCP server here
                log_info(f"Generated schema SQL for {database_path}")
                return [TextContent(type="text", text=json.dumps({
                    "ok": True,
                    "database_path": database_path,
                    "schema_sql": sql_schema,
                    "tables_count": len(tables),
                    "note": "Schema SQL generated. Use SQLite MCP server to actually execute the schema creation."
                }, indent=2))]
            
            elif name == "generate_sql_queries":
                query_type = arguments['query_type']
                table_info = arguments['table_info']
                requirements = arguments['requirements']
                execute = arguments.get('execute', False)
                database_path = arguments.get('database_path', '')
                
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
                response = await client.post(VLLM_API_URL, json={
                    "model": VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.2
                })
                
                result = response.json()
                sql_query = result['choices'][0]['message']['content']
                
                response_data = {
                    "ok": True,
                    "query_type": query_type,
                    "sql_query": sql_query,
                    "requirements": requirements
                }
                
                if execute and database_path:
                    response_data["note"] = "Query generated. Use SQLite MCP server to execute if needed."
                    response_data["database_path"] = database_path
                
                log_info(f"Generated {query_type} SQL query")
                return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
            
            log_error(f"Unknown tool: {name}")
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        log_error(f"Error in call_tool({name}): {e}", exc_info=True)
        raise

async def main():
    from mcp.server.stdio import stdio_server
    
    try:
        log_info("Initializing MCP server...")
        
        # Test vLLM connection
        log_info("Testing vLLM connection...")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:8002/v1/models")
                log_info(f"✓ vLLM connection OK: {response.status_code}")
                log_debug(f"vLLM models response: {response.text}")
        except Exception as e:
            log_error(f"⚠ Cannot connect to vLLM: {e}")
            log_error("Server will start anyway, but tools will fail until vLLM is available")
        
        log_info("Starting stdio server...")
        async with stdio_server() as (read_stream, write_stream):
            log_info("✓ MCP server ready and listening")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except KeyboardInterrupt:
        log_info("Server stopped by user")
    except Exception as e:
        log_error(f"FATAL ERROR in main(): {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_info("Shutting down...")
    except Exception as e:
        log_error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)