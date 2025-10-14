#!/usr/bin/env python3
"""
Main entry point for the vLLM MCP Delegator server
"""

import asyncio
import json
import os
import sys
import time

from mcp.server import Server
from mcp.types import TextContent

# Import configuration
from config.settings import load_config

# Import core components
from core.client import call_vllm_api, vllm_client
from core.metrics import metrics_collector
from tools.analysis_tools import (
    create_analysis_tools,
    execute_analyze_codebase,
    execute_detect_code_smells,
    execute_generate_api_documentation,
    execute_generate_code_review,
    execute_generate_integration_tests,
    execute_generate_performance_analysis,
    execute_generate_unit_test_fixtures,
    execute_security_scan_code,
    execute_suggest_refactoring_opportunities,
)

# Import all tool modules
from tools.base import create_health_check_tool, create_simple_code_tool
from tools.code_tools import (
    create_code_tools,
    execute_add_type_annotations,
    execute_complete_code,
    execute_convert_code_format,
    execute_explain_code,
    execute_fix_simple_bugs,
    execute_generate_docstrings,
    execute_generate_tests,
    execute_improve_code_style,
    execute_optimize_imports,
    execute_refactor_simple_code,
)
from tools.database_tools import (
    create_database_tools,
    execute_create_database_schema,
    execute_generate_sql_queries,
)
from tools.generation_tools import (
    create_generation_tools,
    execute_create_config_file,
    execute_create_directory_structure,
    execute_create_github_issue,
    execute_create_github_pr,
    execute_execute_dev_command,
    execute_generate_boilerplate_file,
    execute_generate_github_workflow,
    execute_generate_gitignore,
    execute_generate_pr_description,
    execute_generate_schema,
)
from tools.git_tools import (
    create_git_tools,
    execute_generate_git_commit_message,
    execute_git_add,
    execute_git_commit,
    execute_git_diff,
    execute_git_log,
    execute_git_smart_commit,
    execute_git_status,
)
from tools.validation_tools import (
    create_validation_tools,
    execute_auto_format_with_black,
    execute_fix_blank_lines,
    execute_fix_complexity_issues,
    execute_fix_docstring_issues,
    execute_fix_import_issues,
    execute_fix_indentation,
    execute_fix_line_endings,
    execute_fix_line_length,
    execute_fix_missing_whitespace,
    execute_fix_mypy_issues,
    execute_fix_naming_conventions,
    execute_fix_security_issues,
    execute_fix_string_quotes,
    execute_fix_syntax_errors,
    execute_fix_trailing_whitespace,
    execute_fix_unused_variables,
    execute_precommit,
    execute_precommit_fix,
)
from utils.logging import log_error, log_info, setup_logging

# Load configuration
CONFIG = load_config()

# Setup logging
logger = setup_logging(CONFIG)

# Initialize server
server = Server("vllm-delegator-enhanced")

log_info(f"vLLM API URL: {CONFIG.vllm.api_url if CONFIG.vllm else 'Not configured'}")
log_info(f"vLLM Model: {CONFIG.vllm.model if CONFIG.vllm else 'Not configured'}")
log_info(
    f"Security: Allowed paths: {len(CONFIG.security.allowed_paths) if CONFIG.security and CONFIG.security.allowed_paths else 0}"
)
log_info(
    f"Features: Caching={CONFIG.features.caching if CONFIG.features else False}, Metrics={CONFIG.features.metrics if CONFIG.features else False}"
)


@server.list_tools()
async def list_tools():
    """List all available tools"""
    log_info("list_tools() called")

    tools = [
        # Base tools
        create_health_check_tool(),
        create_simple_code_tool(),
    ]

    # Add all tool modules
    tools.extend(create_validation_tools())
    tools.extend(create_code_tools())
    tools.extend(create_git_tools())
    tools.extend(create_generation_tools())
    tools.extend(create_analysis_tools())
    tools.extend(create_database_tools())

    log_info(f"Returning {len(tools)} tools")
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute a tool"""
    start_time = time.time()
    log_info(f"call_tool() invoked: {name}")

    try:
        # Base tools
        if name == "health_check":
            return await execute_health_check(arguments)
        elif name == "generate_simple_code":
            return await execute_generate_simple_code(arguments)

        elif name == "precommit":
            return await execute_precommit(arguments, CONFIG)
        # Validation tools
        elif name == "precommit&fix":
            return await execute_precommit_fix(arguments, CONFIG)
        elif name == "fix_line_length":
            return await execute_fix_line_length(arguments, CONFIG)
        elif name == "fix_missing_whitespace":
            return await execute_fix_missing_whitespace(arguments, CONFIG)
        elif name == "fix_import_issues":
            return await execute_fix_import_issues(arguments, CONFIG)
        elif name == "fix_indentation":
            return await execute_fix_indentation(arguments, CONFIG)
        elif name == "fix_blank_lines":
            return await execute_fix_blank_lines(arguments, CONFIG)
        elif name == "fix_trailing_whitespace":
            return await execute_fix_trailing_whitespace(arguments, CONFIG)
        elif name == "fix_string_quotes":
            return await execute_fix_string_quotes(arguments, CONFIG)
        elif name == "fix_line_endings":
            return await execute_fix_line_endings(arguments, CONFIG)
        elif name == "fix_naming_conventions":
            return await execute_fix_naming_conventions(arguments, CONFIG)
        elif name == "fix_unused_variables":
            return await execute_fix_unused_variables(arguments, CONFIG)
        elif name == "fix_docstring_issues":
            return await execute_fix_docstring_issues(arguments, CONFIG)
        elif name == "fix_security_issues":
            return await execute_fix_security_issues(arguments, CONFIG)
        elif name == "fix_complexity_issues":
            return await execute_fix_complexity_issues(arguments, CONFIG)
        elif name == "fix_syntax_errors":
            return await execute_fix_syntax_errors(arguments, CONFIG)
        elif name == "auto_format_with_black":
            return await execute_auto_format_with_black(arguments, CONFIG)
        elif name == "fix_mypy_issues":
            return await execute_fix_mypy_issues(arguments, CONFIG)

        # Code tools
        elif name == "complete_code":
            return await execute_complete_code(arguments, CONFIG)
        elif name == "explain_code":
            return await execute_explain_code(arguments, CONFIG)
        elif name == "generate_docstrings":
            return await execute_generate_docstrings(arguments, CONFIG)
        elif name == "generate_tests":
            return await execute_generate_tests(arguments, CONFIG)
        elif name == "refactor_simple_code":
            return await execute_refactor_simple_code(arguments, CONFIG)
        elif name == "fix_simple_bugs":
            return await execute_fix_simple_bugs(arguments, CONFIG)
        elif name == "convert_code_format":
            return await execute_convert_code_format(arguments, CONFIG)
        elif name == "improve_code_style":
            return await execute_improve_code_style(arguments, CONFIG)
        elif name == "add_type_annotations":
            return await execute_add_type_annotations(arguments, CONFIG)
        elif name == "optimize_imports":
            return await execute_optimize_imports(arguments, CONFIG)

        # Git tools
        elif name == "git_status":
            return await execute_git_status(arguments, CONFIG)
        elif name == "git_add":
            return await execute_git_add(arguments, CONFIG)
        elif name == "git_commit":
            return await execute_git_commit(arguments, CONFIG)
        elif name == "git_diff":
            return await execute_git_diff(arguments, CONFIG)
        elif name == "git_log":
            return await execute_git_log(arguments, CONFIG)
        elif name == "git_smart_commit":
            return await execute_git_smart_commit(arguments, CONFIG)
        elif name == "generate_git_commit_message":
            return await execute_generate_git_commit_message(arguments, CONFIG)

        # Generation tools
        elif name == "generate_boilerplate_file":
            return await execute_generate_boilerplate_file(arguments, CONFIG)
        elif name == "generate_schema":
            return await execute_generate_schema(arguments, CONFIG)
        elif name == "generate_gitignore":
            return await execute_generate_gitignore(arguments, CONFIG)
        elif name == "generate_github_workflow":
            return await execute_generate_github_workflow(arguments, CONFIG)
        elif name == "generate_pr_description":
            return await execute_generate_pr_description(arguments, CONFIG)
        elif name == "create_config_file":
            return await execute_create_config_file(arguments, CONFIG)
        elif name == "create_directory_structure":
            return await execute_create_directory_structure(arguments, CONFIG)
        elif name == "create_github_issue":
            return await execute_create_github_issue(arguments, CONFIG)
        elif name == "create_github_pr":
            return await execute_create_github_pr(arguments, CONFIG)
        elif name == "execute_dev_command":
            return await execute_execute_dev_command(arguments, CONFIG)

        # Analysis tools
        elif name == "analyze_codebase":
            return await execute_analyze_codebase(arguments, CONFIG)
        elif name == "detect_code_smells":
            return await execute_detect_code_smells(arguments, CONFIG)
        elif name == "generate_code_review":
            return await execute_generate_code_review(arguments, CONFIG)
        elif name == "suggest_refactoring_opportunities":
            return await execute_suggest_refactoring_opportunities(arguments, CONFIG)
        elif name == "generate_performance_analysis":
            return await execute_generate_performance_analysis(arguments, CONFIG)
        elif name == "security_scan_code":
            return await execute_security_scan_code(arguments, CONFIG)
        elif name == "generate_api_documentation":
            return await execute_generate_api_documentation(arguments, CONFIG)
        elif name == "generate_integration_tests":
            return await execute_generate_integration_tests(arguments, CONFIG)
        elif name == "generate_unit_test_fixtures":
            return await execute_generate_unit_test_fixtures(arguments, CONFIG)

        # Database tools
        elif name == "create_database_schema":
            return await execute_create_database_schema(arguments, CONFIG)
        elif name == "generate_sql_queries":
            return await execute_generate_sql_queries(arguments, CONFIG)

        else:
            # Unknown tool
            log_error(f"Unknown tool: {name}")
            metrics_collector.record_execution(
                name, start_time, False, error_type="unknown_tool"
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"ok": False, "error": f"Unknown tool: {name}"}, indent=2
                    ),
                )
            ]

    except Exception as e:
        log_error(f"Error in call_tool({name}): {e}", exc_info=True)
        metrics_collector.record_execution(
            name, start_time, False, error_type=type(e).__name__
        )
        return [
            TextContent(
                type="text", text=json.dumps({"ok": False, "error": str(e)}, indent=2)
            )
        ]


async def execute_health_check(arguments: dict):
    """Execute health check"""
    checks = {}

    # Check vLLM connection
    try:
        client = await vllm_client.get_client()
        api_url = (
            CONFIG.vllm.api_url
            if CONFIG.vllm
            else "http://localhost:8002/v1/chat/completions"
        )
        response = await client.get(api_url.replace("/chat/completions", "/models"))
        checks["vllm_connection"] = {
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "response_time": (
                response.elapsed.total_seconds() if hasattr(response, "elapsed") else 0
            ),
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
        "caching_enabled": CONFIG.features.caching if CONFIG.features else False,
        "metrics_enabled": CONFIG.features.metrics if CONFIG.features else False,
        "auto_backup_enabled": (
            CONFIG.features.auto_backup if CONFIG.features else False
        ),
        "allowed_paths": (
            len(CONFIG.security.allowed_paths)
            if CONFIG.security and CONFIG.security.allowed_paths
            else 0
        ),
    }

    return [TextContent(type="text", text=json.dumps(checks, indent=2))]


async def execute_generate_simple_code(arguments: dict):
    """Execute simple code generation"""
    language = arguments.get("language", "python")

    prompt = f"""You are a code generator. Generate clean, working {language} code for the following request.
Only output the code, no explanations unless asked.

Request: {arguments["prompt"]}"""

    log_info("Calling vLLM API for generate_simple_code")
    code = await call_vllm_api(prompt, "code_generation", language, CONFIG)

    log_info(f"Generated {len(code)} characters of code")
    return [TextContent(type="text", text=code)]


async def main():
    """Main entry point"""
    from mcp.server.stdio import stdio_server

    try:
        log_info("Initializing Enhanced MCP server...")

        # Test vLLM connection
        log_info("Testing vLLM connection...")
        try:
            client = await vllm_client.get_client()
            api_url = (
                CONFIG.vllm.api_url
                if CONFIG.vllm
                else "http://localhost:8002/v1/chat/completions"
            )
            response = await client.get(api_url.replace("/chat/completions", "/models"))
            log_info(f"✓ vLLM connection OK: {response.status_code}")
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
