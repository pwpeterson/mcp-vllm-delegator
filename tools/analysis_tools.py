"""
Code analysis and quality tools
"""

import json
import os
from typing import List

from mcp.types import TextContent, Tool

from config.models import LANGUAGE_CONFIGS, detect_project_language
from core.client import call_vllm_api
from security.utils import safe_path
from utils.errors import create_error_response
from utils.logging import log_info


def create_analysis_tools() -> List[Tool]:
    """Create code analysis and quality tool definitions"""
    return [
        Tool(
            name="analyze_codebase",
            description="Analyze codebase structure and provide insights about architecture, patterns, and potential improvements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to analyze",
                        "default": ".",
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["structure", "quality", "patterns", "dependencies"],
                        "default": "structure",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="detect_code_smells",
            description="Use LLM to identify potential code quality issues and technical debt.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to analyze"},
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
            name="generate_code_review",
            description="Automated code review feedback using local LLM. Analyzes code changes and provides structured review comments for style, bugs, performance, and best practices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_diff": {
                        "type": "string",
                        "description": "Git diff or code changes to review",
                    },
                    "review_focus": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Focus areas for review",
                        "default": ["style", "bugs", "performance", "maintainability"],
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "severity_filter": {
                        "type": "string",
                        "enum": ["all", "medium_and_high", "high_only"],
                        "default": "all",
                        "description": "Filter review comments by severity",
                    },
                },
                "required": ["code_diff"],
            },
        ),
        Tool(
            name="suggest_refactoring_opportunities",
            description="Identify specific refactoring opportunities in code using local LLM. Provides ranked suggestions with before/after examples.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to analyze for refactoring",
                    },
                    "refactoring_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of refactoring to look for",
                        "default": [
                            "extract_method",
                            "reduce_complexity",
                            "remove_duplication",
                            "improve_naming",
                        ],
                    },
                    "complexity_threshold": {
                        "type": "integer",
                        "description": "Complexity threshold for suggestions",
                        "default": 10,
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
            name="generate_performance_analysis",
            description="Analyze code for performance bottlenecks using local LLM. Identifies optimization opportunities and algorithmic improvements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to analyze for performance",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "performance_context": {
                        "type": "string",
                        "enum": [
                            "web_api",
                            "data_processing",
                            "real_time",
                            "batch_processing",
                            "general",
                        ],
                        "default": "general",
                        "description": "Performance context for analysis",
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Performance areas to focus on",
                        "default": [
                            "time_complexity",
                            "space_complexity",
                            "io_operations",
                            "database_queries",
                        ],
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="security_scan_code",
            description="Detect security vulnerabilities in code using local LLM. Identifies common security issues with fix suggestions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to scan for security issues",
                    },
                    "vulnerability_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of vulnerabilities to check for",
                        "default": [
                            "injection",
                            "authentication",
                            "authorization",
                            "crypto",
                            "input_validation",
                        ],
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python",
                    },
                    "include_fixes": {
                        "type": "boolean",
                        "description": "Include fix suggestions",
                        "default": True,
                    },
                    "severity_threshold": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium",
                        "description": "Minimum severity level to report",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="generate_api_documentation",
            description="Extract and generate API documentation from code using local LLM. Creates formatted docs with examples.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code containing API definitions",
                    },
                    "doc_format": {
                        "type": "string",
                        "enum": ["openapi", "markdown", "jsdoc", "rustdoc", "sphinx"],
                        "default": "markdown",
                        "description": "Documentation format to generate",
                    },
                    "include_examples": {
                        "type": "boolean",
                        "description": "Include usage examples in documentation",
                        "default": True,
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
            name="generate_integration_tests",
            description="Create integration test suites using local LLM. Generates comprehensive tests for API endpoints and component interactions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to generate integration tests for",
                    },
                    "test_scenarios": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Test scenarios to cover",
                        "default": [
                            "happy_path",
                            "error_cases",
                            "edge_cases",
                            "authentication",
                        ],
                    },
                    "framework": {
                        "type": "string",
                        "enum": [
                            "pytest",
                            "unittest",
                            "jest",
                            "supertest",
                            "testcontainers",
                        ],
                        "default": "pytest",
                        "description": "Testing framework to use",
                    },
                    "include_fixtures": {
                        "type": "boolean",
                        "description": "Include test data fixtures",
                        "default": True,
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
            name="generate_unit_test_fixtures",
            description="Create test data and mock objects using local LLM. Generates realistic test fixtures for unit testing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_under_test": {
                        "type": "string",
                        "description": "Code that needs test fixtures",
                    },
                    "fixture_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of fixtures to generate",
                        "default": [
                            "mock_data",
                            "test_objects",
                            "api_responses",
                            "database_records",
                        ],
                    },
                    "framework": {
                        "type": "string",
                        "enum": ["pytest", "unittest", "jest", "mockito", "sinon"],
                        "default": "pytest",
                        "description": "Testing framework for fixtures",
                    },
                    "data_realism": {
                        "type": "string",
                        "enum": ["simple", "realistic", "comprehensive"],
                        "default": "realistic",
                        "description": "Level of realism for generated data",
                    },
                },
                "required": ["code_under_test"],
            },
        ),
    ]


async def execute_analyze_codebase(arguments: dict, config=None) -> List[TextContent]:
    """Execute codebase analysis"""
    directory = arguments.get("directory", ".")
    analysis_type = arguments.get("analysis_type", "structure")

    # Validate directory path
    try:
        safe_dir = safe_path(".", directory)
    except ValueError as e:
        return create_error_response("analyze_codebase", str(e))

    # Collect codebase information
    try:
        file_info = []
        for root, dirs, files in os.walk(safe_dir):
            for file in files:
                if any(
                    file.endswith(ext)
                    for ext_list in [
                        config["file_extensions"]
                        for config in LANGUAGE_CONFIGS.values()
                    ]
                    for ext in ext_list
                ):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, safe_dir)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = len(f.readlines())
                        file_info.append({"path": relative_path, "lines": lines})
                    except Exception:
                        continue

        # Detect primary language
        primary_language = detect_project_language(safe_dir)

        prompt = f"""Analyze this {primary_language} codebase for {analysis_type}.

Files and structure:
{json.dumps(file_info[:50], indent=2)}

Analysis type: {analysis_type}

Provide insights about:
- Overall architecture and organization
- Code quality indicators
- Potential improvements
- Patterns and anti-patterns observed
- Recommendations for the development team

Total files analyzed: {len(file_info)}
Primary language: {primary_language}"""

        log_info(f"Analyzing codebase: {len(file_info)} files")
        analysis = await call_vllm_api(prompt, "analysis", config=config)

        result = {
            "analysis": analysis,
            "metadata": {
                "directory": directory,
                "files_found": len(file_info),
                "primary_language": primary_language,
                "analysis_type": analysis_type,
            },
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return create_error_response(
            "analyze_codebase", f"Codebase analysis failed: {str(e)}"
        )


async def execute_detect_code_smells(arguments: dict, config=None) -> List[TextContent]:
    """Execute code smell detection"""
    language = arguments.get("language", "python")

    prompt = f"""Analyze this {language} code for potential quality issues and code smells.

Code to analyze:
{arguments["code"]}

Look for:
- Code duplication
- Long methods/functions
- Complex conditionals
- Poor naming conventions
- Missing error handling
- Performance issues
- Security vulnerabilities
- Maintainability concerns

Provide specific recommendations for improvement with examples where possible."""

    log_info("Analyzing code for smells")
    analysis = await call_vllm_api(prompt, "analysis", config=config)

    return [TextContent(type="text", text=analysis)]


async def execute_generate_code_review(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute automated code review"""
    review_focus = arguments.get(
        "review_focus", ["style", "bugs", "performance", "maintainability"]
    )
    language = arguments.get("language", "python")
    severity_filter = arguments.get("severity_filter", "all")

    focus_areas = ", ".join(review_focus)

    prompt = f"""Perform a comprehensive code review of this {language} code diff.

Code changes:
{arguments["code_diff"]}

Focus areas: {focus_areas}
Severity filter: {severity_filter}

Provide structured review feedback including:
1. Code style and formatting issues
2. Potential bugs and logic errors
3. Performance concerns
4. Maintainability improvements
5. Security considerations
6. Best practice violations

For each issue, provide:
- Severity level (low/medium/high/critical)
- Specific location in the code
- Clear explanation of the problem
- Suggested fix or improvement

Format as structured review comments."""

    log_info("Generating automated code review")
    review = await call_vllm_api(prompt, "analysis", config=config)

    return [TextContent(type="text", text=review)]


async def execute_suggest_refactoring_opportunities(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute refactoring opportunity analysis"""
    refactoring_types = arguments.get(
        "refactoring_types",
        ["extract_method", "reduce_complexity", "remove_duplication", "improve_naming"],
    )
    complexity_threshold = arguments.get("complexity_threshold", 10)
    language = arguments.get("language", "python")

    types_str = ", ".join(refactoring_types)

    prompt = f"""Analyze this {language} code for refactoring opportunities.

Code to analyze:
{arguments["code"]}

Refactoring types to look for: {types_str}
Complexity threshold: {complexity_threshold}

Identify specific refactoring opportunities including:
1. Methods/functions that are too long or complex
2. Code duplication that can be extracted
3. Poor naming that reduces readability
4. Complex conditionals that can be simplified
5. Classes with too many responsibilities

For each opportunity, provide:
- Priority level (high/medium/low)
- Specific code location
- Type of refactoring needed
- Expected benefits
- Before/after example (for simple cases)

Rank suggestions by impact and effort required."""

    log_info("Analyzing refactoring opportunities")
    suggestions = await call_vllm_api(prompt, "analysis", config=config)

    return [TextContent(type="text", text=suggestions)]


async def execute_generate_performance_analysis(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute performance analysis"""
    language = arguments.get("language", "python")
    performance_context = arguments.get("performance_context", "general")
    focus_areas = arguments.get(
        "focus_areas",
        ["time_complexity", "space_complexity", "io_operations", "database_queries"],
    )

    areas_str = ", ".join(focus_areas)

    prompt = f"""Analyze this {language} code for performance bottlenecks and optimization opportunities.

Code to analyze:
{arguments["code"]}

Performance context: {performance_context}
Focus areas: {areas_str}

Analyze for:
1. Time complexity issues (O(n²) loops, inefficient algorithms)
2. Space complexity problems (memory leaks, excessive allocations)
3. I/O bottlenecks (file operations, network calls)
4. Database query inefficiencies
5. Synchronous operations that could be async
6. Resource management issues

For each issue found, provide:
- Performance impact level (critical/high/medium/low)
- Specific code location
- Root cause explanation
- Optimization suggestion with example
- Expected performance improvement

Prioritize suggestions by potential impact."""

    log_info("Analyzing code performance")
    analysis = await call_vllm_api(prompt, "analysis", config=config)

    return [TextContent(type="text", text=analysis)]


async def execute_security_scan_code(arguments: dict, config=None) -> List[TextContent]:
    """Execute security vulnerability scan"""
    vulnerability_types = arguments.get(
        "vulnerability_types",
        ["injection", "authentication", "authorization", "crypto", "input_validation"],
    )
    language = arguments.get("language", "python")
    include_fixes = arguments.get("include_fixes", True)
    severity_threshold = arguments.get("severity_threshold", "medium")

    vuln_types_str = ", ".join(vulnerability_types)
    fixes_instruction = (
        "Include specific fix suggestions" if include_fixes else "Identify issues only"
    )

    prompt = f"""Perform a security analysis of this {language} code.

Code to scan:
{arguments["code"]}

Vulnerability types to check: {vuln_types_str}
Severity threshold: {severity_threshold}
{fixes_instruction}

Scan for common security vulnerabilities:
1. Injection attacks (SQL, command, code injection)
2. Authentication bypasses and weak authentication
3. Authorization flaws and privilege escalation
4. Cryptographic issues (weak algorithms, poor key management)
5. Input validation failures
6. Cross-site scripting (XSS) vulnerabilities
7. Insecure direct object references
8. Security misconfigurations

For each vulnerability found, provide:
- Severity level (critical/high/medium/low)
- Vulnerability type and CWE reference if applicable
- Specific code location
- Exploitation scenario
- Impact assessment
- Detailed fix recommendation with secure code example

Only report issues at or above the {severity_threshold} severity threshold."""

    log_info("Scanning code for security vulnerabilities")
    scan_results = await call_vllm_api(prompt, "analysis", config=config)

    return [TextContent(type="text", text=scan_results)]


async def execute_generate_api_documentation(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute API documentation generation"""
    doc_format = arguments.get("doc_format", "markdown")
    include_examples = arguments.get("include_examples", True)
    language = arguments.get("language", "python")

    examples_instruction = (
        "Include usage examples and sample requests/responses"
        if include_examples
        else "Documentation only, no examples"
    )

    prompt = f"""Generate {doc_format} API documentation from this {language} code.

Code containing API definitions:
{arguments["code"]}

{examples_instruction}

Generate comprehensive API documentation including:
1. API overview and purpose
2. Authentication requirements
3. Endpoint descriptions with HTTP methods
4. Request/response schemas
5. Parameter descriptions and validation rules
6. Error codes and responses
7. Usage examples with sample data
8. Rate limiting and other constraints

Format the output as proper {doc_format} documentation."""

    log_info(f"Generating {doc_format} API documentation")
    documentation = await call_vllm_api(prompt, "documentation", config=config)

    return [TextContent(type="text", text=documentation)]


async def execute_generate_integration_tests(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute integration test generation"""
    test_scenarios = arguments.get(
        "test_scenarios", ["happy_path", "error_cases", "edge_cases", "authentication"]
    )
    framework = arguments.get("framework", "pytest")
    include_fixtures = arguments.get("include_fixtures", True)
    language = arguments.get("language", "python")

    scenarios_str = ", ".join(test_scenarios)
    fixtures_instruction = (
        "Include test fixtures and setup/teardown"
        if include_fixtures
        else "Tests only, no fixtures"
    )

    prompt = f"""Generate comprehensive integration tests using {framework} for this {language} code.

Code to test:
{arguments["code"]}

Test scenarios: {scenarios_str}
{fixtures_instruction}

Generate integration tests covering:
1. Happy path scenarios with valid inputs
2. Error handling and edge cases
3. Authentication and authorization flows
4. Data validation and boundary conditions
5. External service interactions
6. Database operations and transactions
7. Concurrent access scenarios

Include:
- Test setup and teardown procedures
- Mock external dependencies
- Test data fixtures
- Assertion strategies
- Error condition testing

Generate complete, runnable test code with proper test organization."""

    log_info(f"Generating integration tests with {framework}")
    tests = await call_vllm_api(prompt, "code_generation", language, config)

    return [TextContent(type="text", text=tests)]


async def execute_generate_unit_test_fixtures(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute unit test fixture generation"""
    fixture_types = arguments.get(
        "fixture_types",
        ["mock_data", "test_objects", "api_responses", "database_records"],
    )
    framework = arguments.get("framework", "pytest")
    data_realism = arguments.get("data_realism", "realistic")

    types_str = ", ".join(fixture_types)

    prompt = f"""Generate test fixtures using {framework} for this code.

Code under test:
{arguments["code_under_test"]}

Fixture types: {types_str}
Data realism level: {data_realism}

Generate test fixtures including:
1. Mock data objects with realistic values
2. Test object instances with various states
3. Sample API responses (success and error)
4. Database record fixtures
5. Configuration and environment fixtures

Ensure fixtures are:
- Realistic and representative of production data
- Varied to cover different test scenarios
- Properly structured for the testing framework
- Reusable across multiple tests
- Include both valid and invalid data samples

Generate complete fixture code with proper setup and organization."""

    log_info(f"Generating test fixtures with {data_realism} data")
    fixtures = await call_vllm_api(prompt, "code_generation", config=config)

    return [TextContent(type="text", text=fixtures)]
