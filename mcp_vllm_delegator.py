# mcp_vllm_delegator.py
import asyncio
import json
import sys
import logging
import os
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