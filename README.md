# vLLM MCP Server for Task Delegation

An MCP (Model Context Protocol) server that enables Claude (via Roo Code) to delegate simple coding tasks to a local vLLM instance running Qwen2.5-Coder. This dramatically improves development speed by offloading boilerplate generation, testing, documentation, and other repetitive tasks to local compute while keeping Claude focused on complex architectural decisions.

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
- **vLLM** running Qwen2.5-Coder in a Podman container
- **Roo Code** VS Code extension
- **MCP Python SDK**: `pip install mcp httpx`

## Installation

### 1. Set Up vLLM Container

```bash
# Pull and run Qwen2.5-Coder with vLLM
podman run -d \
  --name vllm-qwen \
  -p 8000:8000 \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --served-model-name Qwen/Qwen2.5-Coder-7B-Instruct

# Verify it's running
curl http://localhost:8000/v1/models
```

### 2. Install MCP Server

```bash
# Install dependencies
pip install mcp httpx

# Download the MCP server
# Save vllm_mcp_server.py to a location like ~/mcp-servers/
mkdir -p ~/mcp-servers
# Copy vllm_mcp_server.py to ~/mcp-servers/
```

### 3. Configure Roo Code

Create or edit `~/.config/roo-code/mcp.json`:

```json
{
  "mcpServers": {
    "vllm-delegate": {
      "command": "python",
      "args": ["/home/YOUR_USERNAME/mcp-servers/vllm_mcp_server.py"]
    }
  }
}
```

**Note:** Replace `/home/YOUR_USERNAME/` with your actual path.

### 4. Update Roo Code System Prompt

Copy the enhanced system prompt (see `system_prompt.md`) to your Roo Code configuration. This teaches Claude when and how to delegate tasks to the local vLLM.

### 5. Restart Roo Code

Restart VS Code to load the new MCP server configuration.

## Configuration

### Adjusting vLLM API Endpoint

If your vLLM container uses a different port, update the `VLLM_API_URL` in `vllm_mcp_server.py`:

```python
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"  # Change port if needed
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

### Model Selection

To use a different model, update the model name in `vllm_mcp_server.py`:

```python
"model": "Qwen/Qwen2.5-Coder-7B-Instruct",  # Change to your model
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
3. **Local Execution**: vLLM processes the request using Qwen2.5-Coder
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
curl http://localhost:8000/v1/models
```

### MCP Server Not Loading

```bash
# Test the server directly
python ~/mcp-servers/vllm_mcp_server.py

# Check Roo Code logs in VS Code
# View > Output > Select "Roo Code" from dropdown
```

### Port Conflicts

```bash
# Check what's using port 8000
lsof -i :8000

# Use a different port
podman run -p 8001:8000 ...
# Then update VLLM_API_URL in the MCP server
```

### Permission Issues

```bash
# Ensure the script is executable
chmod +x ~/mcp-servers/vllm_mcp_server.py

# Check file permissions
ls -la ~/mcp-servers/
```

## Performance Tips

1. **GPU Acceleration**: Ensure vLLM has access to GPU for faster inference
2. **Model Size**: Use 7B models for balance of speed/quality (14B/32B for better quality)
3. **Batching**: vLLM automatically batches requests for efficiency
4. **Temperature**: Lower temperatures (0.2) for code generation ensure consistency

## Advanced Configuration

### Custom Temperature Settings

Edit the MCP server to adjust temperatures per tool:

```python
"temperature": 0.1  # More deterministic
"temperature": 0.3  # More creative
```

### Adding Custom Tools

Follow the existing pattern in `vllm_mcp_server.py`:

```python
Tool(
    name="your_tool_name",
    description="Clear description of what it does",
    inputSchema={...}
)
```

### Logging

Add logging for debugging:

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add to tool calls
logger.info(f"Processing {name} with args: {arguments}")
```

## Benefits

- **🚀 Speed**: Offload simple tasks to local compute, 2-5x faster for boilerplate
- **💰 Cost**: Reduce API costs by delegating to local LLM
- **🎯 Focus**: Claude focuses on complex problems while vLLM handles repetitive work
- **🔒 Privacy**: Sensitive code stays local
- **⚡ Efficiency**: Parallel processing of simple tasks

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

## Acknowledgments

- **Anthropic** - Claude and MCP protocol
- **vLLM Team** - High-performance LLM inference
- **Qwen Team** - Qwen2.5-Coder model
- **Roo Code** - VS Code extension for agentic coding