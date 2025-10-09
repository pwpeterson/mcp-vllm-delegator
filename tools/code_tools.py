"""
Code generation and manipulation tools
"""

import time
from typing import List

from mcp.types import TextContent, Tool

from config.models import detect_language_from_code
from core.client import call_vllm_api
from core.metrics import metrics_collector
from utils.errors import create_error_response
from utils.logging import log_error, log_info


def create_code_tools() -> List[Tool]:
    """Create code generation and manipulation tool definitions"""
    return [
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
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
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
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
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
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
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
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                },
                "required": ["code", "from_format", "to_format"],
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


async def execute_complete_code(arguments: dict, config=None) -> List[TextContent]:
    """Execute code completion"""
    language = arguments.get("language", "python")
    # Auto-detect language from code context if not specified
    if language == "python":
        language = detect_language_from_code(arguments["code_context"])

    prompt = f"""Complete the following code according to the instruction.

Code:
{arguments['code_context']}

Instruction: {arguments['instruction']}

Provide only the completion, maintaining the existing code style."""

    log_info("Calling vLLM API for complete_code")
    completion = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(completion)} characters of completion")
    return [TextContent(type="text", text=completion)]


async def execute_explain_code(arguments: dict, config=None) -> List[TextContent]:
    """Execute code explanation"""
    detail = "briefly" if arguments.get("detail_level") == "brief" else "in detail"
    prompt = f"""Explain {detail} what this code does:

{arguments['code']}"""

    log_info("Calling vLLM API for explain_code")
    explanation = await call_vllm_api(prompt, "explanation", config=config)

    log_info(f"Generated {len(explanation)} characters of explanation")
    return [TextContent(type="text", text=explanation)]


async def execute_generate_docstrings(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute docstring generation"""
    style = arguments.get("style", "google")
    language = arguments.get("language", "python")
    prompt = f"""Add {style}-style docstrings to this {language} code. Return the complete code with docstrings added.

{arguments['code']}

Follow {style} documentation standards for {language}. Include parameter descriptions, return values, and any exceptions that might be raised."""

    log_info("Calling vLLM API for generate_docstrings")
    documented_code = await call_vllm_api(prompt, "documentation", config=config)

    log_info(f"Generated {len(documented_code)} characters of documented code")
    return [TextContent(type="text", text=documented_code)]


async def execute_generate_tests(arguments: dict, config=None) -> List[TextContent]:
    """Execute test generation"""
    framework = arguments.get("test_framework", "pytest")
    coverage = arguments.get("coverage_level", "standard")
    language = arguments.get("language", "python")

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
    tests = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(tests)} characters of tests")
    return [TextContent(type="text", text=tests)]


async def execute_refactor_simple_code(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute simple code refactoring"""
    language = arguments.get("language", "python")
    context = arguments.get("additional_context", "")
    context_str = f"\n\nAdditional context: {context}" if context else ""

    prompt = f"""Refactor the following code using this refactoring pattern: {arguments['refactor_type']}
{context_str}

Original code:
{arguments['code']}

Provide the refactored code, maintaining functionality."""

    log_info("Calling vLLM API for refactor_simple_code")
    refactored = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(refactored)} characters of refactored code")
    return [TextContent(type="text", text=refactored)]


async def execute_fix_simple_bugs(arguments: dict, config=None) -> List[TextContent]:
    """Execute simple bug fixing"""
    language = arguments.get("language", "python")
    context = arguments.get("context", "")
    context_str = f"\n\nAdditional context: {context}" if context else ""

    prompt = f"""Fix the bug in this code.

Error message: {arguments['error_message']}
{context_str}

Code with bug:
{arguments['code']}

Provide the corrected code with a brief explanation of the fix."""

    log_info("Calling vLLM API for fix_simple_bugs")
    fixed_code = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(fixed_code)} characters of fixed code")
    return [TextContent(type="text", text=fixed_code)]


async def execute_convert_code_format(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute code format conversion"""
    language = arguments.get("language", "python")

    prompt = f"""Convert this code from {arguments['from_format']} to {arguments['to_format']}.

Original code:
{arguments['code']}

Provide only the converted code."""

    log_info("Calling vLLM API for convert_code_format")
    converted = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(converted)} characters of converted code")
    return [TextContent(type="text", text=converted)]


async def execute_improve_code_style(arguments: dict, config=None) -> List[TextContent]:
    """Execute code style improvement"""
    style_guide = arguments.get("style_guide", "pep8")
    language = arguments.get("language", "python")

    prompt = f"""Improve the code style following {style_guide} guidelines for {language}.
Focus on: naming conventions, formatting, readability, and best practices.

Original code:
{arguments['code']}

Provide the improved code."""

    log_info("Calling vLLM API for improve_code_style")
    improved = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(improved)} characters of improved code")
    return [TextContent(type="text", text=improved)]


async def execute_add_type_annotations(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute type annotation addition"""
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
    annotated_code = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(annotated_code)} characters of annotated code")
    return [TextContent(type="text", text=annotated_code)]


async def execute_optimize_imports(arguments: dict, config=None) -> List[TextContent]:
    """Execute import optimization"""
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
    optimized_code = await call_vllm_api(prompt, "code_generation", language, config)

    log_info(f"Generated {len(optimized_code)} characters of optimized code")
    return [TextContent(type="text", text=optimized_code)]
