"""
Git operations and workflow tools
"""

import json
import subprocess
import time
from typing import List

from mcp.types import TextContent, Tool

from core.client import call_vllm_api
from core.metrics import metrics_collector
from security.utils import validate_command
from utils.errors import create_error_response
from utils.logging import log_error, log_info


def create_git_tools() -> List[Tool]:
    """Create git operation tool definitions"""
    return [
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
    ]


async def execute_git_status(arguments: dict, config=None) -> List[TextContent]:
    """Execute git status command"""
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
            return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
        else:
            return [TextContent(type="text", text=output)]

    except subprocess.CalledProcessError as e:
        error_msg = f"Git status failed: {e.stderr}"
        log_error(error_msg)
        return create_error_response("git_status", error_msg)


async def execute_git_add(arguments: dict, config=None) -> List[TextContent]:
    """Execute git add command"""
    files = arguments.get("files", [])
    if not files:
        return create_error_response("git_add", "No files specified")

    cmd = ["git", "add"] + files

    # Validate command
    allowed_commands = (
        config.security.allowed_commands if config and config.security else None
    )
    if not validate_command(cmd, allowed_commands):
        return create_error_response("git_add", "Git add command not allowed")

    log_info(f"Executing: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_info(f"Git add completed successfully")
        response_data = {
            "ok": True,
            "output": result.stdout.strip(),
            "cmd": " ".join(cmd),
        }
        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

    except subprocess.CalledProcessError as e:
        error_msg = f"Git add failed: {e.stderr}"
        log_error(error_msg)
        return create_error_response("git_add", error_msg)


async def execute_git_commit(arguments: dict, config=None) -> List[TextContent]:
    """Execute git commit command"""
    message = arguments.get("message", "")
    auto_push = arguments.get("auto_push", True)

    if not message:
        return create_error_response("git_commit", "Commit message required")

    cmd = ["git", "commit", "-m", message]

    # Validate command
    allowed_commands = (
        config.security.allowed_commands if config and config.security else None
    )
    if not validate_command(cmd, allowed_commands):
        return create_error_response("git_commit", "Git commit command not allowed")

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
            if validate_command(push_cmd, allowed_commands):
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
            else:
                response_data["push"] = {
                    "ok": False,
                    "error": "Push command not allowed",
                }

        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

    except subprocess.CalledProcessError as e:
        error_msg = f"Git commit failed: {e.stderr}"
        log_error(error_msg)
        return create_error_response("git_commit", error_msg)


async def execute_git_diff(arguments: dict, config=None) -> List[TextContent]:
    """Execute git diff command"""
    staged = arguments.get("staged", False)
    files = arguments.get("files", [])

    cmd = ["git", "diff"]
    if staged:
        cmd.append("--cached")
    cmd.extend(files)

    # Validate command
    allowed_commands = (
        config.security.allowed_commands if config and config.security else None
    )
    if not validate_command(cmd, allowed_commands):
        return create_error_response("git_diff", "Git diff command not allowed")

    log_info(f"Executing: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        log_info(f"Git diff completed successfully")
        return [
            TextContent(
                type="text",
                text=output if output else "No differences found",
            )
        ]

    except subprocess.CalledProcessError as e:
        error_msg = f"Git diff failed: {e.stderr}"
        log_error(error_msg)
        return create_error_response("git_diff", error_msg)


async def execute_git_log(arguments: dict, config=None) -> List[TextContent]:
    """Execute git log command"""
    limit = arguments.get("limit", 10)
    oneline = arguments.get("oneline", True)

    cmd = ["git", "log", f"-{limit}"]
    if oneline:
        cmd.append("--oneline")

    # Validate command
    allowed_commands = (
        config.security.allowed_commands if config and config.security else None
    )
    if not validate_command(cmd, allowed_commands):
        return create_error_response("git_log", "Git log command not allowed")

    log_info(f"Executing: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        log_info(f"Git log completed successfully")
        return [TextContent(type="text", text=output if output else "No commits found")]

    except subprocess.CalledProcessError as e:
        error_msg = f"Git log failed: {e.stderr}"
        log_error(error_msg)
        return create_error_response("git_log", error_msg)


async def execute_git_smart_commit(arguments: dict, config=None) -> List[TextContent]:
    """Execute smart commit with auto-generated message"""
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
                return create_error_response("git_smart_commit", "No changes to commit")

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
        commit_message = await call_vllm_api(prompt, "git_commit", config=config)
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

        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

    except subprocess.CalledProcessError as e:
        error_msg = f"Git operation failed: {e.stderr}"
        return create_error_response("git_smart_commit", error_msg)


async def execute_generate_git_commit_message(
    arguments: dict, config=None
) -> List[TextContent]:
    """Generate git commit message"""
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
    commit_message = await call_vllm_api(prompt, "git_commit", config=config)
    commit_message = commit_message.strip()

    log_info(f"Generated commit message: {commit_message[:50]}...")
    return [TextContent(type="text", text=commit_message)]
