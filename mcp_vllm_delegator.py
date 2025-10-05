# mcp_vllm_delegator.py
import asyncio
import json
import sys
import logging
import os
import subprocess
from mcp.server import Server
from mcp.types import Tool, TextContent
import httpx

# ========== CONFIGURABLE LOGGING SETUP ==========
# Check environment variables for logging control
LOGGING_ENABLED = os.getenv('LOGGING_ON', 'false').lower() in ('true', '1', 'yes', 'on')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.getenv('LOG_FILE', '/tmp/vllm_mcp_delegator.log')

if LOGGING_ENABLED:
    # Create log directory if it doesn't exist
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
    # Minimal/no-op logging when disabled
    logging.basicConfig(
        level=logging.ERROR,
        format='%(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]
    )
    logger = logging.getLogger(__name__)

# Helper functions for conditional logging
def log_info(msg):
    if LOGGING_ENABLED:
        logger.info(msg)

def log_debug(msg):
    if LOGGING_ENABLED:
        logger.debug(msg)

def log_error(msg, exc_info=False):
    logger.error(msg, exc_info=exc_info)

# Adjust this to your vLLM container's exposed port
VLLM_API_URL = "http://localhost:8002/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"

log_info(f"vLLM API URL: {VLLM_API_URL}")
log_info(f"vLLM Model: {VLLM_MODEL}")

server = Server("vllm-delegator")

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
                        "default": false
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
                        "default": true
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
                        "default": true
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
                        "default": false
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
                        "default": true
                    }
                },
                "required": []
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
        async with httpx.AsyncClient(timeout=60.0) as client:
            
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