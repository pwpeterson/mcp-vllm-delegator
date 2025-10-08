# MCP vLLM Delegator

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.16.0+-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that enables Claude to delegate simple coding tasks to your local vLLM instance running Qwen2.5-Coder. This dramatically speeds up development by offloading boilerplate generation, documentation, testing, and other routine tasks to local compute while keeping Claude focused on architecture and complex logic.

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+**
- **GPU with 20GB+ VRAM** (for 32B model) or 8GB+ (for 7B model)
- **Docker/Podman** for vLLM container
- **Claude via Roo Code** or other MCP-compatible client

### 1. Start vLLM Server

```bash
# Start Qwen2.5-Coder-32B-AWQ (recommended)
podman run -d \
  --name vllm-qwen \
  -p 8002:8000 \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --served-model-name Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --quantization awq

# Verify it's running
curl http://localhost:8002/v1/models
```

### 2. Install Dependencies

```bash
pip install mcp httpx
```

### 3. Configure MCP Client

For **Roo Code**, add to `~/.config/roo-code/mcp.json`:

```json
{
  "mcpServers": {
    "vllm-delegator": {
      "command": "python",
      "args": ["/path/to/vllm_delegator.py"]
    }
  }
}
```

### 4. Test the Connection

```bash
python test_delegator.py
```

## 🎯 What It Does

### Tasks Delegated to Local vLLM

✅ **Code Generation**
- Boilerplate code (CRUD operations, basic models)
- Simple utility functions
- Standard implementations (getters/setters, parsers)
- Configuration files (.gitignore, Dockerfiles, workflows)

✅ **Documentation & Testing**
- Docstrings (Google, NumPy, Sphinx, JSDoc styles)
- Unit tests (pytest, unittest, jest, mocha)
- Git commit messages
- PR descriptions

✅ **Code Maintenance**
- Simple refactoring (extract method, rename variables)
- Style improvements (PEP8, Black, Prettier)
- Format conversions (camelCase↔snake_case, JSON↔YAML)
- Bug fixes for syntax errors and simple logic issues

✅ **Schema Generation**
- Pydantic models
- SQLAlchemy schemas
- TypeScript interfaces
- GraphQL schemas
- JSON Schema
- Protocol Buffers

### Tasks Handled by Claude

🧠 **Architecture & Design**
- System design decisions
- Complex algorithms
- Security-sensitive code
- Performance optimization
- Integration between systems

## 🛠️ Available Tools

### Code Generation (11 tools)
- `generate_simple_code` - Basic code generation
- `complete_code` - Fill in function bodies, complete classes
- `explain_code` - Quick code explanations
- `generate_docstrings` - Documentation in multiple styles
- `generate_tests` - Unit tests for various frameworks
- `refactor_simple_code` - Simple refactoring patterns
- `fix_simple_bugs` - Fix syntax errors and simple logic bugs
- `convert_code_format` - Format/style conversions
- `generate_boilerplate_file` - Complete file templates
- `improve_code_style` - Apply style guides
- `generate_schema` - Data models and schemas

### Git & GitHub Operations (9 tools)
- `generate_git_commit_message` - Conventional commit messages
- `generate_gitignore` - Language-specific .gitignore files
- `generate_github_workflow` - CI/CD workflow files
- `generate_pr_description` - Comprehensive PR descriptions
- `git_status` - Execute git status with parsed output
- `git_add` - Stage files for commit
- `git_commit` - Commit with message (auto-push enabled)
- `git_diff` - Show changes (staged or unstaged)
- `git_log` - Show commit history

### Project & File Operations (6 tools)
- `create_config_file` - Generate config files
- `create_directory_structure` - Project scaffolding
- `create_github_issue` - Generate issue bodies
- `create_github_pr` - Generate PR content
- `execute_dev_command` - Run development commands
- `create_database_schema` - SQLite schema generation
- `generate_sql_queries` - SQL query generation

## 📊 Performance Benefits

### Response Times (32B-AWQ on RTX 4090)

| Task Type | Local vLLM | Claude Direct | Speedup |
|-----------|------------|---------------|----------|
| Simple function | 2-4 seconds | 8-12 seconds | **3x faster** |
| Boilerplate file | 3-6 seconds | 15-25 seconds | **4x faster** |
| Test generation | 4-8 seconds | 12-20 seconds | **3x faster** |
| Documentation | 2-4 seconds | 8-15 seconds | **4x faster** |
| Git operations | 1-3 seconds | 5-10 seconds | **3x faster** |

### Quality Comparison

| Aspect | Local vLLM (32B) | Claude |
|--------|-------------------|--------|
| Code correctness | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Style consistency | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Boilerplate quality | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Complex logic | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Context awareness | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## 💡 Usage Examples

### Example 1: Generate a REST API Endpoint

**User:** "Create a FastAPI endpoint for user registration"

**Claude:** "Delegating boilerplate generation to local Qwen2.5-Coder..."

```python
# Generated by vLLM, reviewed by Claude
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter()

class UserRegistration(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

@router.post("/register")
async def register_user(user_data: UserRegistration):
    # Validation and registration logic here
    return {"message": "User registered successfully"}
```

**Result:** Generated with local LLM, reviewed and verified

### Example 2: Add Comprehensive Tests

**User:** "Add tests for this authentication function"

**Claude:** "Delegating test generation to local Qwen2.5-Coder..."

```python
# Generated comprehensive pytest tests
import pytest
from unittest.mock import Mock, patch

def test_authenticate_valid_credentials():
    # Happy path test
    pass

def test_authenticate_invalid_password():
    # Error case test
    pass

def test_authenticate_nonexistent_user():
    # Edge case test
    pass
```

### Example 3: Git Workflow

**User:** "Review changes and commit with appropriate message"

**Claude:** 
1. Reviews `git_status` and `git_diff`
2. "Delegating commit message generation to local Qwen2.5-Coder..."
3. Uses `generate_git_commit_message`
4. Commits with `git_commit`

**Result:** `feat(api): add user registration endpoint with validation`

## 🔧 Configuration

### Environment Variables

```bash
# Logging (optional)
export LOGGING_ON=true
export LOG_LEVEL=INFO
export LOG_FILE=/tmp/vllm_mcp_delegator.log

# vLLM Configuration (defaults shown)
export VLLM_API_URL=http://localhost:8002/v1/chat/completions
export VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
```

### Model Options

| Model | VRAM Required | Quality | Speed |
|-------|---------------|---------|-------|
| Qwen2.5-Coder-32B-Instruct-AWQ | 20GB+ | Excellent | Good |
| Qwen2.5-Coder-14B-Instruct | 12GB+ | Very Good | Better |
| Qwen2.5-Coder-7B-Instruct | 8GB+ | Good | Best |

## 🚨 Troubleshooting

### Common Issues

**"Connection refused to localhost:8002"**
```bash
# Check if vLLM container is running
podman ps | grep vllm-qwen

# Start if stopped
podman start vllm-qwen

# Check logs
podman logs vllm-qwen
```

**"Out of memory" error**
```bash
# Check GPU memory
nvidia-smi

# Use smaller model
podman run -d --name vllm-qwen -p 8002:8000 --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-7B-Instruct
```

**"Tool execution timeout"**
- Increase timeout in `vllm_delegator.py`
- Check vLLM server performance
- Consider using smaller model

### Debug Mode

```bash
# Enable detailed logging
export LOGGING_ON=true
export LOG_LEVEL=DEBUG

# Run with debug output
python vllm_delegator.py
```

## 📁 Project Structure

```
mcp-vllm-delegator/
├── vllm_delegator.py      # Main MCP server
├── test_delegator.py      # Connection test
├── test_tool_call.py      # Tool testing
├── pyproject.toml         # Project configuration
├── README.md              # This file
├── Quickstart_Guide.md    # Step-by-step setup
├── Usage_Scenarios.md     # Real-world examples
└── context_portal/        # ConPort integration
```

## 🤝 Integration with Other Tools

### ConPort Memory System
The delegator integrates with ConPort for project memory:
- Logs successful delegation patterns
- Tracks code generation decisions
- Builds knowledge graph of project patterns

### Compatible MCP Clients
- **Roo Code** (VS Code extension)
- **Claude Desktop** (with MCP support)
- **Custom MCP clients**

## 🔄 Development Workflow

### Daily Usage
1. Start vLLM container: `podman start vllm-qwen`
2. Open your MCP-enabled editor
3. Let Claude delegate routine tasks automatically
4. Focus on architecture and complex logic

### Best Practices
- **Trust Claude's delegation decisions** - it knows what to delegate
- **Review delegated output** - always verify generated code
- **Batch similar tasks** - group related work for efficiency
- **Iterate quickly** - start simple, refine in steps

## 📈 Monitoring

### Performance Metrics
```bash
# vLLM metrics
curl http://localhost:8002/metrics

# GPU utilization
watch -n 1 nvidia-smi

# Container logs
podman logs -f vllm-qwen
```

### Usage Analytics
Look for these indicators in Claude's responses:
- "Generated with local LLM, reviewed and verified"
- "Delegating [task] to local Qwen2.5-Coder..."
- Faster response times for routine tasks

## 🛣️ Roadmap

- [ ] **Multi-model support** - Support for different code models
- [ ] **Custom tool creation** - Project-specific delegation tools
- [ ] **Performance optimization** - Caching and batching improvements
- [ ] **Quality metrics** - Automated quality assessment
- [ ] **Team collaboration** - Shared delegation patterns

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

### Development Setup

```bash
git clone https://github.com/your-org/mcp-vllm-delegator.git
cd mcp-vllm-delegator
pip install -e .

# Run tests
python test_delegator.py
python test_tool_call.py
```

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **Qwen Team** for the excellent Qwen2.5-Coder models
- **vLLM Team** for the high-performance inference engine
- **Anthropic** for Claude and MCP protocol
- **Model Context Protocol** community

## 📚 Additional Resources

- [Quickstart Guide](Quickstart_Guide.md) - Step-by-step setup
- [Usage Scenarios](Usage_Scenarios.md) - Real-world examples
- [MCP Protocol Documentation](https://modelcontextprotocol.io/docs)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Qwen2.5-Coder Paper](https://qwenlm.github.io/blog/qwen2.5-coder/)

---

**Ready to supercharge your development workflow?** 🚀

Start with the [Quickstart Guide](Quickstart_Guide.md) and see real examples in [Usage Scenarios](Usage_Scenarios.md).

*Happy coding with your AI pair programmer!* 🤖✨