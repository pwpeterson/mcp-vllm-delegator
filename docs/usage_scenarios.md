# vLLM Delegator Usage Scenarios

Real-world examples showing how Claude delegates tasks to your local vLLM instance.

---
s
## 🏗️ Scenario 1: Building a REST API from Scratch

### User Request
```
"Create a FastAPI application for a blog platform with posts, comments, and users.
Include CRUD operations for all entities."
```

### What Claude Does

**Step 1: Architecture Analysis** (Claude handles)
- Identifies three main entities: User, Post, Comment
- Plans database schema relationships
- Determines endpoint structure

**Step 2: Generate Models** (Delegates to vLLM)
```python
# Claude uses: generate_schema for each entity
# Tool calls:
# 1. generate_schema(description="User model with id, email, username, created_at",
#                    schema_type="pydantic")
# 2. generate_schema(description="Post model with id, title, content, author_id, created_at",
#                    schema_type="pydantic")
# 3. generate_schema(description="Comment model with id, post_id, user_id, content, created_at",
#                    schema_type="pydantic")
```

**Step 3: Generate CRUD Endpoints** (Delegates to vLLM)
```python
# Claude uses: generate_boilerplate_file for each entity
# Tool call:
# generate_boilerplate_file(
#     file_type="rest_api_route",
#     language="python",
#     options={"framework": "fastapi", "entity": "Post", "operations": ["create", "read", "update", "delete"]}
# )
```

**Step 4: Integration & Review** (Claude handles)
- Reviews generated code for consistency
- Adds proper error handling
- Adds database connection logic
- Adds authentication middleware
- Writes comprehensive docstrings

**Step 5: Testing** (Delegates to vLLM)
```python
# Claude uses: generate_tests for each endpoint
# generate_tests(
#     code="[Post CRUD endpoints]",
#     test_framework="pytest",
#     coverage_level="comprehensive"
# )
```

### Result
Complete, production-ready FastAPI application in 2-3 minutes instead of 30+ minutes of typing boilerplate.

---

## 🐛 Scenario 2: Debugging a Cryptic Error

### User Request
```
"This function crashes with 'list index out of range'. Here's the code:

def process_data(items):
    result = []
    for i in range(len(items)):
        if items[i]['status'] == 'active':
            result.append(items[i]['value'] * items[i+1]['multiplier'])
    return result
"
```

### What Claude Does

**Step 1: Initial Analysis** (Claude handles)
- Identifies the logical error (accessing i+1)
- Understands the intent

**Step 2: Fix the Bug** (Delegates to vLLM)
```python
# Claude uses: fix_simple_bugs
# fix_simple_bugs(
#     code="[original code]",
#     error_message="list index out of range",
#     context="Trying to access next item's multiplier in loop"
# )
```

**Step 3: Review Fix** (Claude handles)
- Verifies the fix is correct
- Suggests additional improvements (use enumerate, bounds checking)
- Explains why the error occurred

**Step 4: Add Tests** (Delegates to vLLM)
```python
# Claude uses: generate_tests
# generate_tests(
#     code="[fixed code]",
#     test_framework="pytest",
#     coverage_level="comprehensive"  # To catch similar edge cases
# )
```

### Result
Fixed code with explanation + comprehensive tests to prevent regression.

---

## 📚 Scenario 3: Legacy Code Documentation

### User Request
```
"This codebase has zero documentation. Start with this module:"
[pastes 200-line module with no docstrings]
```

### What Claude Does

**Step 1: Code Analysis** (Claude handles)
- Reads and understands the code structure
- Identifies key functions and their purposes
- Notes any complex logic requiring detailed explanation

**Step 2: Generate Docstrings** (Delegates to vLLM)
```python
# Claude uses: generate_docstrings
# For each major function/class:
# generate_docstrings(
#     code="[function code]",
#     style="google",
#     language="python"
# )
```

**Step 3: Review & Enhance** (Claude handles)
- Reviews generated docstrings for accuracy
- Adds type hints if missing
- Adds usage examples for complex functions
- Identifies and documents side effects

**Step 4: Create Module Documentation** (Claude handles)
- Writes module-level docstring
- Creates README with usage examples
- Documents any gotchas or limitations

### Result
Fully documented module with consistent style, ready for team collaboration.

---

## 🔄 Scenario 4: Code Refactoring Marathon

### User Request
```
"This 500-line Python file is a mess. Help me refactor it."
[pastes monolithic file with repeated code, no structure]
```

### What Claude Does

**Step 1: Strategic Planning** (Claude handles)
- Analyzes code structure
- Identifies repeated patterns
- Plans refactoring strategy
- Breaks down into manageable chunks

**Step 2: Extract Utility Functions** (Delegates to vLLM)
```python
# Claude uses: refactor_simple_code multiple times
# refactor_simple_code(
#     code="[repeated validation logic]",
#     refactor_type="extract method",
#     additional_context="Create validate_email and validate_phone utilities"
# )
```

**Step 3: Simplify Complex Logic** (Delegates to vLLM)
```python
# Claude uses: refactor_simple_code
# refactor_simple_code(
#     code="[nested if statements]",
#     refactor_type="simplify conditionals",
#     additional_context="Use early returns and guard clauses"
# )
```

**Step 4: Improve Style** (Delegates to vLLM)
```python
# Claude uses: improve_code_style
# improve_code_style(
#     code="[refactored code]",
#     style_guide="black",
#     language="python"
# )
```

**Step 5: Architecture Review** (Claude handles)
- Reorganizes into classes/modules
- Adds proper separation of concerns
- Implements design patterns where appropriate
- Reviews for SOLID principles

**Step 6: Add Tests** (Delegates to vLLM)
```python
# Claude uses: generate_tests
# For each extracted function:
# generate_tests(
#     code="[new function]",
#     test_framework="pytest",
#     coverage_level="standard"
# )
```

### Result
Clean, maintainable codebase with proper structure, tests, and documentation.

---

## 🚀 Scenario 5: Rapid Prototyping

### User Request
```
"I need a proof of concept for a URL shortener service. Quick and dirty, just to demo the concept."
```

### What Claude Does

**Step 1: Quick Design** (Claude handles)
- Plans minimal viable features
- Chooses simple tech stack (FastAPI + SQLite)

**Step 2: Generate Core Components** (Delegates to vLLM)
```python
# Parallel delegation:
# 1. generate_schema(description="URLMapping with short_code, original_url, created_at",
#                    schema_type="pydantic")
# 2. generate_boilerplate_file(file_type="database_model", language="python",
#                               options={"orm": "sqlalchemy", "table": "url_mappings"})
# 3. generate_simple_code(prompt="FastAPI endpoint to create short URL and return short code")
# 4. generate_simple_code(prompt="FastAPI endpoint to redirect from short code to original URL")
```

**Step 3: Quick Integration** (Claude handles)
- Connects components
- Adds basic error handling
- Creates simple landing page HTML

**Step 4: Quick Tests** (Delegates to vLLM)
```python
# Claude uses: generate_tests
# generate_tests(
#     code="[complete API]",
#     test_framework="pytest",
#     coverage_level="basic"  # Just happy path for POC
# )
```

### Result
Working URL shortener in under 5 minutes, ready for demo.

---

## 🎨 Scenario 6: Style Consistency Across Team

### User Request
```
"Our team uses different code styles. Standardize these 5 files to match our style guide."
[pastes 5 files with inconsistent formatting]
```

### What Claude Does

**Step 1: Analyze Current Styles** (Claude handles)
- Identifies style inconsistencies
- Confirms target style guide (e.g., Google Python Style)

**Step 2: Batch Style Improvements** (Delegates to vLLM)
```python
# Claude uses: improve_code_style for each file
# For file in files:
#     improve_code_style(
#         code="[file content]",
#         style_guide="google",
#         language="python"
#     )
```

**Step 3: Add Missing Documentation** (Delegates to vLLM)
```python
# Claude uses: generate_docstrings
# For each file needing docs:
#     generate_docstrings(
#         code="[styled code]",
#         style="google",
#         language="python"
#     )
```

**Step 4: Verify Consistency** (Claude handles)
- Reviews all files for consistency
- Creates style guide document
- Sets up pre-commit hooks config

### Result
5 files formatted consistently, documented uniformly, with tooling to maintain standards.

---

## 🔧 Scenario 7: Converting Between Frameworks

### User Request
```
"We're migrating from Flask to FastAPI. Convert these 10 Flask routes."
[pastes Flask application code]
```

### What Claude Does

**Step 1: Migration Planning** (Claude handles)
- Analyzes Flask patterns used
- Plans FastAPI equivalents
- Identifies potential issues

**Step 2: Convert Routes** (Delegates to vLLM)
```python
# Claude uses: convert_code_format for each route
# For each Flask route:
#     convert_code_format(
#         code="[Flask route]",
#         from_format="flask",
#         to_format="fastapi"
#     )
```

**Step 3: Update Models** (Delegates to vLLM)
```python
# Claude uses: generate_schema
# For each model:
#     generate_schema(
#         description="[extracted from Flask model]",
#         schema_type="pydantic"
#     )
```

**Step 4: Migration Review** (Claude handles)
- Verifies converted code
- Updates middleware and dependencies
- Adapts authentication/authorization
- Updates configuration

**Step 5: Generate Migration Tests** (Delegates to vLLM)
```python
# Claude uses: generate_tests
# generate_tests(
#     code="[FastAPI routes]",
#     test_framework="pytest",
#     coverage_level="comprehensive"
# )
```

### Result
Complete Flask → FastAPI migration with tests ensuring feature parity.

---

## 📊 Scenario 8: Data Processing Pipeline

### User Request
```
"Build a data processing pipeline that reads CSV files, validates data, transforms it, and loads to PostgreSQL."
```

### What Claude Does

**Step 1: Pipeline Architecture** (Claude handles)
- Designs pipeline stages
- Plans error handling strategy
- Determines data validation rules

**Step 2: Generate Pipeline Components** (Delegates to vLLM)
```python
# Claude uses: generate_simple_code for each stage
# 1. CSV reader utility
# 2. Data validator class
# 3. Data transformer functions
# 4. Database loader class
```

**Step 3: Generate Data Models** (Delegates to vLLM)
```python
# Claude uses: generate_schema
# generate_schema(
#     description="[from CSV headers]",
#     schema_type="pydantic"  # For validation
# )
# generate_schema(
#     description="[same structure]",
#     schema_type="sqlalchemy"  # For database
# )
```

**Step 4: Integration & Error Handling** (Claude handles)
- Connects pipeline stages
- Adds comprehensive error handling
- Implements logging
- Adds retry logic

**Step 5: Generate Tests** (Delegates to vLLM)
```python
# Claude uses: generate_tests
# For each component + integration tests
```

### Result
Robust data pipeline with validation, error handling, and comprehensive tests.

---

## 🎓 Scenario 9: Learning New Framework

### User Request
```
"I'm new to FastAPI. Show me how to build a simple todo app with authentication."
```

### What Claude Does

**Step 1: Educational Planning** (Claude handles)
- Structures learning progression
- Plans minimal but complete example

**Step 2: Generate Basic Structure** (Delegates to vLLM)
```python
# Claude uses: generate_boilerplate_file
# generate_boilerplate_file(
#     file_type="rest_api_route",
#     language="python",
#     options={"framework": "fastapi", "features": ["crud", "auth"]}
# )
```

**Step 3: Add Explanations** (Claude handles)
- Explains each part of generated code
- Highlights FastAPI-specific patterns
- Points out best practices

**Step 4: Generate Examples** (Delegates to vLLM)
```python
# Claude uses: generate_simple_code
# For various concepts:
# - Dependency injection example
# - Pydantic model example
# - JWT authentication example
```

**Step 5: Create Learning Tests** (Delegates to vLLM)
```python
# Claude uses: generate_tests
# generate_tests(
#     code="[todo app]",
#     test_framework="pytest",
#     coverage_level="comprehensive"
# )
# Tests serve as usage examples!
```

### Result
Complete, working FastAPI application with explanations and tests as learning materials.

---

## 🔐 Scenario 10: Security Audit & Fixes

### User Request
```
"Audit this authentication module for security issues."
[pastes auth code with potential vulnerabilities]
```

### What Claude Does

**Step 1: Security Analysis** (Claude handles)
- Identifies security issues (SQL injection, weak hashing, etc.)
- Prioritizes vulnerabilities by severity
- Plans remediation

**Step 2: Fix Simple Issues** (Delegates to vLLM)
```python
# Claude uses: fix_simple_bugs for obvious fixes
# fix_simple_bugs(
#     code="[vulnerable code]",
#     error_message="Potential SQL injection in user query",
#     context="Use parameterized queries"
# )
```

**Step 3: Complex Security Fixes** (Claude handles)
- Implements proper password hashing
- Adds input sanitization
- Implements rate limiting
- Adds CSRF protection

**Step 4: Generate Security Tests** (Delegates to vLLM)
```python
# Claude uses: generate_tests
# generate_tests(
#     code="[secured auth module]",
#     test_framework="pytest",
#     coverage_level="comprehensive"
# )
# Focuses on security test cases
```

**Step 5: Documentation** (Delegates to vLLM)
```python
# Claude uses: generate_docstrings
# Adds security considerations to docs
```

### Result
Secured authentication module with vulnerability fixes and security-focused tests.

---

## 💡 Key Patterns Across Scenarios

### When Claude Delegates:
- ✅ Boilerplate generation
- ✅ Simple refactoring
- ✅ Test generation
- ✅ Documentation
- ✅ Format conversions
- ✅ Style improvements

### When Claude Handles:
- 🧠 Architecture decisions
- 🧠 Complex logic
- 🧠 Security considerations
- 🧠 Integration work
- 🧠 Error handling strategies
- 🧠 Code review & quality

### Efficiency Gains:
- **Boilerplate**: 5-10x faster
- **Tests**: 3-5x faster
- **Documentation**: 4-6x faster
- **Refactoring**: 2-4x faster
- **Overall**: 2-3x faster development

---

## 🎯 Best Practices from Scenarios

1. **Let Claude Decide**: Trust Claude to identify delegatable tasks
2. **Review Everything**: Always review delegated output
3. **Batch Similar Tasks**: Group similar work for parallel delegation
4. **Iterate Quickly**: Start simple, refine in iterations
5. **Combine Tools**: Use multiple tools for complete solutions
6. **Document Intent**: Clear requests get better delegation

---

## 🚀 Try These Next

1. **Your Own Scenario**: Apply patterns to your current project
2. **Mix & Match**: Combine scenarios (e.g., prototype + refactor + test)
3. **Custom Workflows**: Create project-specific delegation patterns
4. **Team Templates**: Save successful patterns for team reuse

Happy coding with your AI pair programmer! 🤖✨
