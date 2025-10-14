"""
Database and SQL tools
"""

import json
import sqlite3
from typing import List

from mcp.types import TextContent, Tool

from core.client import call_vllm_api
from security.utils import safe_path
from utils.errors import create_error_response
from utils.logging import log_info


def create_database_tools() -> List[Tool]:
    """Create database and SQL tool definitions"""
    return [
        Tool(
            name="create_database_schema",
            description="Generate and execute SQLite database schema creation using local LLM. Use for: table creation, index creation, basic schema setup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_path": {
                        "type": "string",
                        "description": "Path to SQLite database file",
                    },
                    "schema_description": {
                        "type": "string",
                        "description": "Description of the schema to create",
                    },
                    "tables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                            },
                        },
                        "description": "Table specifications",
                        "default": [],
                    },
                },
                "required": ["database_path", "schema_description"],
            },
        ),
        Tool(
            name="generate_sql_queries",
            description="Generate common SQL queries using local LLM. Use for: CRUD operations, data analysis queries, reporting queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "select",
                            "insert",
                            "update",
                            "delete",
                            "create_table",
                            "create_index",
                            "analytics",
                        ],
                        "description": "Type of SQL query to generate",
                    },
                    "table_info": {
                        "type": "string",
                        "description": "Information about tables and columns involved",
                    },
                    "requirements": {
                        "type": "string",
                        "description": "Specific requirements for the query",
                    },
                    "execute": {
                        "type": "boolean",
                        "description": "Whether to execute the query (for safe operations only)",
                        "default": False,
                    },
                    "database_path": {
                        "type": "string",
                        "description": "Database path (required if execute=true)",
                        "default": "",
                    },
                },
                "required": ["query_type", "table_info", "requirements"],
            },
        ),
    ]


async def execute_create_database_schema(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute database schema creation"""
    database_path = arguments.get("database_path")
    schema_description = arguments.get("schema_description")
    tables = arguments.get("tables", [])

    # Validate database path
    try:
        safe_db_path = safe_path(".", database_path)
    except ValueError as e:
        return create_error_response("create_database_schema", str(e))

    # Generate schema SQL
    tables_info = (
        "\n".join([f"- {table['name']}: {table['description']}" for table in tables])
        if tables
        else "No specific tables provided"
    )

    prompt = f"""Generate SQLite database schema SQL for the following requirements:

Schema description: {schema_description}

Tables to create:
{tables_info}

Generate complete SQL statements including:
1. CREATE TABLE statements with appropriate data types
2. Primary keys and foreign key constraints
3. Indexes for performance
4. Any necessary triggers or views
5. Sample INSERT statements for initial data (optional)

Ensure the schema follows SQLite best practices and includes proper constraints.
Provide only the SQL statements, no explanations."""

    log_info("Generating database schema SQL")
    schema_sql = await call_vllm_api(prompt, "code_generation", config=config)

    try:
        # Create database and execute schema
        conn = sqlite3.connect(safe_db_path)
        cursor = conn.cursor()

        # Execute the generated SQL
        cursor.executescript(schema_sql)
        conn.commit()

        # Get table info for verification
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables_created = [row[0] for row in cursor.fetchall()]

        conn.close()

        response_data = {
            "ok": True,
            "database_path": safe_db_path,
            "tables_created": tables_created,
            "schema_sql": schema_sql,
            "tables_count": len(tables_created),
        }

        log_info(
            f"Created database schema at {safe_db_path} with {len(tables_created)} tables"
        )
        return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

    except sqlite3.Error as e:
        return create_error_response(
            "create_database_schema", f"Database error: {str(e)}"
        )
    except Exception as e:
        return create_error_response(
            "create_database_schema", f"Failed to create schema: {str(e)}"
        )


async def execute_generate_sql_queries(
    arguments: dict, config=None
) -> List[TextContent]:
    """Execute SQL query generation"""
    query_type = arguments.get("query_type")
    table_info = arguments.get("table_info")
    requirements = arguments.get("requirements")
    execute_query = arguments.get("execute", False)
    database_path = arguments.get("database_path", "")

    # Generate SQL query
    prompt = f"""Generate a {query_type} SQL query based on the following requirements:

Table information:
{table_info}

Query requirements:
{requirements}

Generate optimized SQL that:
1. Follows SQL best practices
2. Uses appropriate indexes and joins
3. Includes proper error handling where applicable
4. Is secure against SQL injection
5. Performs efficiently

For SELECT queries, include:
- Appropriate WHERE clauses
- Proper JOIN syntax
- ORDER BY and LIMIT as needed
- Aggregate functions if required

For INSERT/UPDATE/DELETE queries, include:
- Proper data validation
- Transaction handling recommendations
- Conflict resolution strategies

Provide only the SQL query, no explanations."""

    log_info(f"Generating {query_type} SQL query")
    sql_query = await call_vllm_api(prompt, "code_generation", config=config)

    response_data = {
        "query_type": query_type,
        "generated_sql": sql_query,
        "executed": False,
    }

    # Execute query if requested and safe
    if execute_query and database_path:
        if query_type.lower() in ["select", "create_table", "create_index"]:
            try:
                safe_db_path = safe_path(".", database_path)

                conn = sqlite3.connect(safe_db_path)
                cursor = conn.cursor()

                if query_type.lower() == "select":
                    cursor.execute(sql_query)
                    results = cursor.fetchall()
                    column_names = (
                        [description[0] for description in cursor.description]
                        if cursor.description
                        else []
                    )

                    response_data["results"] = {
                        "columns": column_names,
                        "rows": results,
                        "row_count": len(results),
                    }
                else:
                    cursor.execute(sql_query)
                    conn.commit()
                    response_data["rows_affected"] = cursor.rowcount

                response_data["executed"] = True
                conn.close()

                log_info(f"Successfully executed {query_type} query")

            except ValueError as e:
                response_data["execution_error"] = f"Path validation error: {str(e)}"
            except sqlite3.Error as e:
                response_data["execution_error"] = f"Database error: {str(e)}"
            except Exception as e:
                response_data["execution_error"] = f"Execution error: {str(e)}"
        else:
            response_data["execution_error"] = (
                f"Query type '{query_type}' not allowed for execution (security restriction)"
            )
    elif execute_query:
        response_data["execution_error"] = "Database path required for query execution"

    log_info(f"Generated {query_type} SQL query")
    return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
