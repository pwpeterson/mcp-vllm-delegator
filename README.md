# vLLM MCP Server for Task Delegation

An MCP (Model Context Protocol) server that enables Claude (via Roo Code) to delegate simple coding tasks to a local vLLM instance running Qwen2.5-Coder-32B-Instruct-AWQ. This dramatically improves development speed by offloading boilerplate generation, testing, documentation, and other repetitive tasks to local compute while keeping Claude focused on complex architectural decisions.

## Features

### 🚀 11 Specialized Tools

**Code Generation & Completion**
- `generate_simple_code` - Generate boilerplate, utilities, and standard implementations
- `complete_code` - Fill in function bodies, complete classes, add implementations
- `generate_boilerplate_file` - Create complete files (APIs, models, configs, Dockerfiles)

**Documentation & Testing**
- `generate_docstrings` - Auto-generate docs (Google, NumPy, Sphinx, JSDoc, Rustdoc styles)
- `generate_tests` - Create unit tests with configurable coverage (pytest, unittest, jest, etc.)
- `explain_code` - Quick explanations for code snippets

**Code Quality & Refactoring**
- `refactor_simple_code` - Extract methods, rename variables, simplify conditionals
- `fix_simple_bugs` - Quick fixes for syntax errors and simple logic issues
- `improve_code_style` - Apply style guides (PEP8, Black, Airbnb, Google, Prettier)

**Conversions & Schema Generation**
- `convert_code_format` - Format conversions (camelCase↔snake_case, JSON↔YAML, etc.)
- `generate_schema` - Data models (Pydantic, SQLAlchemy, GraphQL, TypeScript, Protobuf)

## Prerequisites

- **Python 3.8+**
- **vLLM** running Qwen2.5-Coder-32B-Instruct-AWQ in a Podman container
- **Roo Code** VS Code extension
- **MCP Python SDK**: `pip install mcp httpx`

## Installation

### 1. Set Up vLLM Container

```bash
# Pull and run Qwen2.5-Coder-32B-Instruct-AWQ with vLLM
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

**Note:** The 32B AWQ model requires significant VRAM (typically 20-24GB). If you have limited GPU memory, consider using the 7B or 14B models instead.

### 2. Install MCP Server

```bash
# Install dependencies
pip install mcp httpx

# Save mcp_vllm_delegator.py to your preferred location
mkdir -p ~/mcp-servers
# Copy mcp_vllm_delegator.py to ~/mcp-servers/
```

### 3. Configure Roo Code

Create or edit `~/.config/roo-code/mcp.json`:

```json
{
  "mcpServers": {
    "vllm-delegator": {
      "command": "python",
      "args": ["/home/YOUR_USERNAME/mcp-servers/mcp_vllm_delegator.py"]
    }
  }
}
```

**Note:** Replace `/home/YOUR_USERNAME/` with your actual path.

### 4. Update Roo Code System Prompt

Update your Roo Code system prompt to reference the correct server name **`vllm-delegator`** (not `vllm-delegate`). The system prompt should include:

**vLLM Tools Available (server: vllm-delegator):**
- generate_simple_code
- complete_code
- explain_code
- generate_docstrings
- generate_tests
- refactor_simple_code
- fix_simple_bugs
- convert_code_format
- generate_boilerplate_file
- improve_code_style
- generate_schema

### 5. Restart Roo Code

Restart VS Code to load the new MCP server configuration.

## Configuration

### Current Configuration

The provided `mcp_vllm_delegator.py` is configured with:
- **API URL**: `http://localhost:8002/v1/chat/completions`
- **Model**: `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ`
- **Server Name**: `vllm-delegator`
- **Logging**: Controlled via environment variables

### Logging Configuration

Control logging behavior through environment variables in your MCP config:

**Disable Logging (Production)**
```json
{
  "mcpServers": {
    "vllm-delegator": {
      "command": "/home/YOUR_USERNAME/srv/coding_agent/mcp/mcp-vllm-delegator/.venv/bin/python",
      "args": ["/home/YOUR_USERNAME/srv/coding_agent/mcp/mcp-vllm-delegator/mcp_vllm_delegator.py"],
      "env": {
        "LOGGING_ON": "false"
      }
    }
  }
}
```

**Enable Logging (Debugging)**
```json
{
  "mcpServers": {
    "vllm-delegator": {
      "command": "/home/YOUR_USERNAME/srv/coding_agent/mcp/mcp-vllm-delegator/.venv/bin/python",
      "args": ["/home/YOUR_USERNAME/srv/coding_agent/mcp/mcp-vllm-delegator/mcp_vllm_delegator.py"],
      "env": {
        "LOGGING_ON": "true",
        "LOG_LEVEL": "INFO",
        "LOG_FILE": "/home/YOUR_USERNAME/srv/coding_agent/mcp/mcp-vllm-delegator/logs/delegator.log"
      }
    }
  }
}
```

**Available Environment Variables:**
- `LOGGING_ON`: `"true"` or `"false"` (default: `"false"`)
- `LOG_LEVEL`: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` (default: `"INFO"`)
- `LOG_FILE`: Path to log file (default: `/tmp/vllm_mcp_delegator.log`)

**Log Levels:**
- `ERROR`: Only errors (minimal, always enabled)
- `INFO`: Tool calls, vLLM requests, startup messages
- `DEBUG`: Full request/response details, arguments

**Viewing Logs:**
```bash
# Watch logs in real-time
tail -f /tmp/vllm_mcp_delegator.log

# Or your custom log location
tail -f /home/YOUR_USERNAME/srv/coding_agent/mcp/mcp-vllm-delegator/logs/delegator.log
```

### Adjusting vLLM API Endpoint

If you need to change the port, update `VLLM_API_URL` in `mcp_vllm_delegator.py`:

```python
VLLM_API_URL = "http://localhost:8002/v1/chat/completions"  # Change port if needed
```

### Switching Models

To use a different model size, update both the container command and the Python file:

```bash
# For 7B model (lower VRAM requirements)
podman run -d \
  --name vllm-qwen \
  -p 8002:8000 \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-7B-Instruct
```

Then update `VLLM_MODEL` in `mcp_vllm_delegator.py`:
```python
VLLM_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
```

### Container Networking

If localhost doesn't work:

```bash
# Option 1: Use host networking
podman run --network host ...

# Option 2: Find container IP
podman inspect vllm-qwen | grep IPAddress
# Then update VLLM_API_URL to use the container IP
```

## Usage Examples

Once configured, Claude will automatically use these tools when appropriate:

### Generate Tests
```
User: "Add comprehensive tests for the user authentication module"
Claude: [Uses generate_tests tool with coverage_level="comprehensive"]
```

### Create Boilerplate
```
User: "Create a FastAPI CRUD endpoint for products"
Claude: [Uses generate_boilerplate_file with type="rest_api_route"]
```

### Refactor Code
```
User: "Extract this repeated logic into a helper function"
Claude: [Uses refactor_simple_code with type="extract method"]
```

### Add Documentation
```
User: "Add Google-style docstrings to all functions"
Claude: [Uses generate_docstrings with style="google"]
```

### Fix Bugs
```
User: "Fix the TypeError in this function"
Claude: [Uses fix_simple_bugs with the error message]
```

## How It Works

1. **Task Analysis**: Claude analyzes incoming requests and determines task complexity
2. **Delegation Decision**: Simple, repetitive tasks are delegated to vLLM via MCP tools
3. **Local Execution**: vLLM processes the request using Qwen2.5-Coder-32B-Instruct-AWQ
4. **Review & Integration**: Claude reviews the generated code, makes improvements, and integrates it
5. **Quality Assurance**: Claude ensures code quality, handles edge cases, and maintains consistency

## Delegation Strategy

**Claude Delegates:**
- Boilerplate code (CRUD, models, configs)
- Simple utility functions
- Test generation
- Documentation
- Code formatting/style improvements
- Basic refactoring

**Claude Handles:**
- Architectural decisions
- Complex algorithms
- Security-sensitive code
- Cross-file refactoring
- Integration logic
- Code review and quality improvements

## Troubleshooting

### vLLM Not Responding

```bash
# Check container status
podman ps | grep vllm

# Check logs
podman logs vllm-qwen

# Test API directly
curl http://localhost:8002/v1/models
```

### MCP Server Not Loading

```bash
# Test the server manually with logging enabled
LOGGING_ON=true python ~/mcp-servers/mcp_vllm_delegator.py

# Check the logs for errors
tail -f /tmp/vllm_mcp_delegator.log

# Check Roo Code logs in VS Code
# View > Output > Select "Roo Code" from dropdown
```

### Port Conflicts

```bash
# Check what's using port 8002
lsof -i :8002

# Use a different port
podman run -p 8003:8000 ...
# Then update VLLM_API_URL in the MCP server
```

### Out of Memory (OOM) Errors

The 32B model requires substantial VRAM:

```bash
# Check GPU memory
nvidia-smi

# If OOM, try smaller model or enable tensor parallelism
podman run -d \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --tensor-parallel-size 2  # Split across 2 GPUs
```

### Permission Issues

```bash
# Ensure the script is executable
chmod +x ~/mcp-servers/mcp_vllm_delegator.py

# Check file permissions
ls -la ~/mcp-servers/
```

## Performance Tips

1. **GPU Acceleration**: The 32B AWQ model requires GPU with 20-24GB VRAM
2. **Quantization**: AWQ quantization provides ~2x speedup with minimal quality loss
3. **Model Size Trade-offs**:
   - **7B**: Fast, 6-8GB VRAM, good for simple tasks
   - **14B**: Balanced, 12-14GB VRAM, better reasoning
   - **32B-AWQ**: Best quality, 20-24GB VRAM, near-GPT-4 level coding
4. **Batching**: vLLM automatically batches requests for efficiency
5. **Temperature**: Lower temperatures (0.2) for code generation ensure consistency

## Advanced Configuration

### Custom Temperature Settings

Edit the MCP server to adjust temperatures per tool:

```python
"temperature": 0.1  # More deterministic
"temperature": 0.3  # More creative
```

### Adding Custom Tools

Follow the existing pattern in `mcp_vllm_delegator.py`:

```python
Tool(
    name="your_tool_name",
    description="Clear description of what it does",
    inputSchema={...}
)
```

### Logging for Debugging

Add logging to track tool usage and debug issues:

**Enable via Environment Variables:**
```json
{
  "mcpServers": {
    "vllm-delegator": {
      "command": "/home/YOUR_USERNAME/.venv/bin/python",
      "args": ["/home/YOUR_USERNAME/mcp_vllm_delegator.py"],
      "env": {
        "LOGGING_ON": "true",
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

**Watch logs:**
```bash
tail -f /tmp/vllm_mcp_delegator.log
```

**Disable logging for production:**
```json
"env": {
  "LOGGING_ON": "false"
}
```

### Multi-GPU Setup

For better performance with multiple GPUs:

```bash
podman run -d \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --tensor-parallel-size 2  # Number of GPUs
```

## Benefits

- **🚀 Speed**: Offload simple tasks to local compute, 2-5x faster for boilerplate
- **💰 Cost**: Reduce API costs by delegating to local LLM
- **🎯 Focus**: Claude focuses on complex problems while local LLM handles repetitive work
- **🔒 Privacy**: Sensitive code stays local
- **⚡ Efficiency**: Parallel processing of simple tasks
- **🎨 Quality**: 32B model provides near-GPT-4 level code generation

## Model Comparison

| Model | VRAM | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| 7B | 6-8GB | Fast | Good | Simple tasks, boilerplate |
| 14B | 12-14GB | Medium | Better | General coding, refactoring |
| 32B-AWQ | 20-24GB | Slower | Excellent | Complex logic, best quality |

## System Requirements

**Minimum (7B model):**
- GPU: 8GB VRAM (RTX 3070, A4000)
- RAM: 16GB
- Storage: 10GB

**Recommended (32B-AWQ model):**
- GPU: 24GB VRAM (RTX 3090, RTX 4090, A5000)
- RAM: 32GB
- Storage: 25GB

## Contributing

To add new tools:

1. Add tool definition to `list_tools()`
2. Add implementation to `call_tool()`
3. Update this README with usage examples
4. Test with various inputs

## License

MIT License - Feel free to modify and distribute

## Support

For issues:
- vLLM: https://github.com/vllm-project/vllm
- MCP Protocol: https://modelcontextprotocol.io
- Roo Code: Check extension documentation
- Qwen Models: https://github.com/QwenLM/Qwen2.5-Coder

## Acknowledgments

- **Anthropic** - Claude and MCP protocol
- **vLLM Team** - High-performance LLM inference
- **Qwen Team** - Qwen2.5-Coder models
- **Roo Code** - VS Code extension for agentic coding

## Additional Resources

- [vLLM Documentation](https://docs.vllm.ai/)
- [Qwen2.5-Coder Paper](https://arxiv.org/abs/2409.12186)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [AWQ Quantization](https://github.com/mit-han-lab/llm-awq)