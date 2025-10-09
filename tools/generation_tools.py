"""
File and project generation tools
"""

import json
import os
import subprocess
from typing import List

from mcp.types import TextContent, Tool

from core.client import call_vllm_api
from security.utils import safe_path, validate_command
from utils.errors import create_error_response
from utils.logging import log_error, log_info


def create_generation_tools() -> List[Tool]:
    """Create file and project generation tool definitions"""
    return [
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
    ]


async def execute_generate_boilerplate_file(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute boilerplate file generation"""
    language = arguments.get("language", "python")
    options_str = json.dumps(arguments.get("options", {}), indent=2)

    prompt = f"""Generate a complete {arguments['file_type']} file in {language}.

Options: {options_str}

Generate production-ready, well-structured boilerplate code."""

    log_info("Calling vLLM API for generate_boilerplate_file")
    boilerplate = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(boilerplate)} characters of boilerplate")
    return [TextContent(type="text", text=boilerplate)]


async def execute_generate_schema(arguments: dict, config=None) -> List[TextContent]:
    """Execute schema generation"""
    language = arguments.get("language", "python")

    prompt = f"""Generate a {arguments['schema_type']} schema in {language} based on this description:

{arguments['description']}

Generate complete, well-typed schema code."""

    log_info("Calling vLLM API for generate_schema")
    schema = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(schema)} characters of schema")
    return [TextContent(type="text", text=schema)]


async def execute_generate_gitignore(arguments: dict, config=None) -> List[TextContent]:
    """Execute .gitignore generation"""
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
    gitignore = await call_vllm_api(prompt, "code_generation", config=config)

    log_info(f"Generated {len(gitignore)} characters of .gitignore")
    return [TextContent(type="text", text=gitignore)]


async def execute_generate_github_workflow(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute GitHub workflow generation"""
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
    workflow = await call_vllm_api(prompt, "code_generation", config=config)

    log_info(f"Generated {len(workflow)} characters of workflow")
    return [TextContent(type="text", text=workflow)]


async def execute_generate_pr_description(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute PR description generation"""
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
    pr_description = await call_vllm_api(prompt, "documentation", config=config)

    log_info(f"Generated {len(pr_description)} characters of PR description")
    return [TextContent(type="text", text=pr_description)]


async def execute_create_config_file(arguments: dict, config=None) -> List[TextContent]:
    """Execute config file creation"""
    file_type = arguments.get("file_type")
    path = arguments.get("path")
    options = arguments.get("options", {})
    custom_prompt = arguments.get("custom_prompt", "")

    # Validate path
    try:
        safe_file_path = safe_path(".", path)
    except ValueError as e:
        return create_error_response("create_config_file", str(e))

    if file_type == "custom" and custom_prompt:
        prompt = custom_prompt
    else:
        options_str = json.dumps(options, indent=2)
        prompt = f"""Generate a {file_type} configuration file.

Options: {options_str}

Generate a complete, production-ready configuration file with appropriate defaults and comments."""

    log_info(f"Generating {file_type} config file")
    content = await call_vllm_api(prompt, "code_generation", config=config)

    # Write file
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(safe_file_path), exist_ok=True)

        with open(safe_file_path, "w") as f:
            f.write(content)

        response_data = {
            "ok": True,
            "file_created": safe_file_path,
            "file_type": file_type,
            "content_length": len(content),
        }

        log_info(f"Created {file_type} file at {safe_file_path}")
        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

    except Exception as e:
        return create_error_response(
            "create_config_file", f"Failed to write file: {str(e)}"
        )


async def execute_create_directory_structure(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute directory structure creation"""
    structure_type = arguments.get("structure_type")
    base_path = arguments.get("base_path")
    project_name = arguments.get("project_name")
    options = arguments.get("options", {})

    # Validate base path
    try:
        safe_base_path = safe_path(".", base_path)
    except ValueError as e:
        return create_error_response("create_directory_structure", str(e))

    options_str = json.dumps(options, indent=2)
    prompt = f"""Generate a directory structure for a {structure_type} project named '{project_name}'.

Options: {options_str}

Provide a JSON structure with directories and files to create. Format:
{{
  "directories": ["dir1", "dir2/subdir"],
  "files": {{
    "file1.txt": "content",
    "dir/file2.py": "# Python file content"
  }}
}}"""

    log_info(f"Generating {structure_type} directory structure")
    structure_json = await call_vllm_api(prompt, "code_generation", config=config)

    try:
        structure = json.loads(structure_json)
        project_path = os.path.join(safe_base_path, project_name)

        # Create project directory
        os.makedirs(project_path, exist_ok=True)

        # Create directories
        for directory in structure.get("directories", []):
            dir_path = os.path.join(project_path, directory)
            os.makedirs(dir_path, exist_ok=True)

        # Create files
        for file_path, content in structure.get("files", {}).items():
            full_file_path = os.path.join(project_path, file_path)
            os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
            with open(full_file_path, "w") as f:
                f.write(content)

        response_data = {
            "ok": True,
            "project_path": project_path,
            "directories_created": len(structure.get("directories", [])),
            "files_created": len(structure.get("files", {})),
        }

        log_info(f"Created {structure_type} project structure at {project_path}")
        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

    except json.JSONDecodeError:
        return create_error_response(
            "create_directory_structure", "Failed to parse LLM response as JSON"
        )
    except Exception as e:
        return create_error_response(
            "create_directory_structure", f"Failed to create structure: {str(e)}"
        )


async def execute_create_github_issue(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute GitHub issue creation (generates content only)"""
    labels_str = ", ".join(arguments.get("labels", []))

    prompt = f"""Generate a GitHub issue for a {arguments['issue_type']} in repository {arguments['repository']}.

Title: {arguments['title']}
Description: {arguments['description']}
Labels: {labels_str}

Generate a well-formatted issue body with:
- Clear problem description
- Steps to reproduce (for bugs)
- Expected behavior
- Additional context
- Acceptance criteria (for features)

Use markdown formatting."""

    log_info("Generating GitHub issue content")
    issue_body = await call_vllm_api(prompt, "documentation", config=config)

    response_data = {
        "repository": arguments["repository"],
        "title": arguments["title"],
        "body": issue_body,
        "labels": arguments.get("labels", []),
        "issue_type": arguments["issue_type"],
    }

    log_info(f"Generated GitHub issue content for {arguments['repository']}")
    return [TextContent(type="text", text=json.dumps(response_data, indent=2))]


async def execute_create_github_pr(arguments: dict, config=None) -> List[TextContent]:
    """Execute GitHub PR creation (generates content only)"""
    prompt = f"""Generate a GitHub pull request for a {arguments['pr_type']} in repository {arguments['repository']}.

Title: {arguments['title']}
Changes: {arguments['changes_summary']}
From: {arguments['head_branch']} → {arguments.get('base_branch', 'main')}

Generate a comprehensive PR description with:
- Summary of changes
- Motivation and context
- Type of change
- Testing performed
- Checklist for reviewers

Use markdown formatting."""

    log_info("Generating GitHub PR content")
    pr_body = await call_vllm_api(prompt, "documentation", config=config)

    response_data = {
        "repository": arguments["repository"],
        "title": arguments["title"],
        "body": pr_body,
        "head_branch": arguments["head_branch"],
        "base_branch": arguments.get("base_branch", "main"),
        "pr_type": arguments["pr_type"],
    }

    log_info(f"Generated GitHub PR content for {arguments['repository']}")
    return [TextContent(type="text", text=json.dumps(response_data, indent=2))]


async def execute_execute_dev_command(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute development command"""
    command_type = arguments.get("command_type")
    args = arguments.get("arguments", [])
    working_dir = arguments.get("working_directory", ".")
    custom_command = arguments.get("custom_command", "")

    # Validate working directory
    try:
        safe_working_dir = safe_path(".", working_dir)
    except ValueError as e:
        return create_error_response("execute_dev_command", str(e))

    # Build command
    if command_type == "custom":
        if not custom_command:
            return create_error_response(
                "execute_dev_command", "Custom command required"
            )
        cmd = custom_command.split() + args
    else:
        command_map = {
            "npm_install": ["npm", "install"],
            "pip_install": ["pip", "install"],
            "cargo_build": ["cargo", "build"],
            "go_mod_tidy": ["go", "mod", "tidy"],
            "make": ["make"],
            "test": ["pytest"] if command_type == "test" else ["test"],
        }

        if command_type not in command_map:
            return create_error_response(
                "execute_dev_command", f"Unknown command type: {command_type}"
            )

        cmd = command_map[command_type] + args

    # Validate command
    allowed_commands = (
        config.security.allowed_commands if config and config.security else None
    )
    if not validate_command(cmd, allowed_commands):
        return create_error_response("execute_dev_command", "Command not allowed")

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

        log_info(f"Command completed with return code {result.returncode}")
        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

    except subprocess.TimeoutExpired:
        return create_error_response(
            "execute_dev_command", "Command timed out after 5 minutes"
        )
    except Exception as e:
        return create_error_response(
            "execute_dev_command", f"Command execution failed: {str(e)}"
        )
