# vLLM Delegator Quickstart Guide

Get Claude delegating tasks to your local vLLM in under 10 minutes!

## ⚡ Quick Setup (5 Steps)

### Step 1: Start vLLM Container (2 minutes)

```bash
# Start Qwen2.5-Coder-32B-AWQ
podman run -d \
  --name vllm-qwen \
  -p 8002:8000 \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --served-model-name Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --quantization awq

# Verify it's running (should return model info)
curl http://localhost:8002/v1/models
```

**First time?** The model download takes 10-15 minutes (20GB). Grab coffee! ☕

### Step 2: Install MCP Dependencies (30 seconds)

```bash
pip install mcp httpx
```

### Step 3: Deploy MCP Server (1 minute)

```bash
# Create directory
mkdir -p ~/mcp-servers

# Save mcp_vllm_delegator.py to ~/mcp-servers/
# (Copy the file you already have)

# Make it executable
chmod +x ~/mcp-servers/mcp_vllm_delegator.py

# Quick test
python ~/mcp-servers/mcp_vllm_delegator.py &
# Should start without errors. Kill it with Ctrl+C
```

### Step 4: Configure Roo Code (1 minute)

```bash
# Create/edit config
mkdir -p ~/.config/roo-code
nano ~/.config/roo-code/mcp.json
```

Paste this:
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

**Don't forget:** Replace `YOUR_USERNAME` with your actual username!

### Step 5: Update System Prompt (2 minutes)

Copy the enhanced system prompt (from `system_prompt.md`) into your Roo Code settings.

**Key section to verify:**
```
**vLLM Tools Available (server: vllm-delegator):**
- generate_simple_code
- complete_code
- generate_tests
...
```

### Step 6: Restart & Test! (1 minute)

1. Restart VS Code
2. Open Roo Code
3. Try: **"Generate a simple FastAPI hello world endpoint"**

Claude should delegate to vLLM and return the code! 🎉

---

## 🎯 First Tasks to Try

### 1. Generate Boilerplate
```
You: "Create a Pydantic model for a User with email, name, and created_at fields"
```

**Expected:** Claude delegates to `generate_simple_code`, reviews output, presents clean model.

### 2. Add Documentation
```
You: "Add docstrings to this function:"
[paste your function]
```

**Expected:** Claude uses `generate_docstrings`, returns documented code.

### 3. Create Tests
```
You: "Write comprehensive tests for this calculator function:"
[paste your function]
```

**Expected:** Claude uses `generate_tests` with comprehensive coverage.

### 4. Fix a Bug
```
You: "This code throws 'TypeError: unsupported operand type(s)'"
[paste buggy code]
```

**Expected:** Claude uses `fix_simple_bugs`, explains the fix.

### 5. Refactor Code
```
You: "Extract the validation logic into a separate function"
[paste code with inline validation]
```

**Expected:** Claude uses `refactor_simple_code`, returns refactored version.

---

## 🔍 Verification Checklist

Use this to verify everything is working:

### ✅ vLLM Container Health
```bash
# Container running?
podman ps | grep vllm-qwen

# API responding?
curl http://localhost:8002/v1/models | jq

# Recent logs look good?
podman logs --tail 20 vllm-qwen
```

### ✅ MCP Server Status
```bash
# Python can find MCP?
python -c "import mcp; print('MCP installed')"

# Server file exists and is executable?
ls -la ~/mcp-servers/mcp_vllm_delegator.py
```

### ✅ Roo Code Configuration
```bash
# Config file exists?
cat ~/.config/roo-code/mcp.json

# Path is correct?
# Should show your actual home directory path
```

### ✅ Claude Integration
In Roo Code:
1. Start a new chat
2. Type: "Can you list the tools available to you?"
3. Look for `vllm-delegator` tools in the response

---

## 🚨 Troubleshooting Quick Fixes

### Problem: "Connection refused to localhost:8002"

```bash
# Check if vLLM is actually running
podman ps

# If not running, start it
podman start vllm-qwen

# Check logs for errors
podman logs vllm-qwen
```

### Problem: "Out of memory" error

```bash
# Check GPU memory
nvidia-smi

# Option 1: Use smaller model (7B)
podman stop vllm-qwen
podman rm vllm-qwen
podman run -d \
  --name vllm-qwen \
  -p 8002:8000 \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-7B-Instruct

# Update VLLM_MODEL in mcp_vllm_delegator.py:
# VLLM_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"

# Option 2: Enable tensor parallelism (if you have 2+ GPUs)
podman run -d \
  --gpus all \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --tensor-parallel-size 2
```

### Problem: "MCP server not found"

```bash
# Check the path in your config
cat ~/.config/roo-code/mcp.json

# Test the server manually
python ~/mcp-servers/mcp_vllm_delegator.py
# Should start without errors
```

### Problem: Claude doesn't use the tools

Check your system prompt includes:
```
**Task Delegation Strategy**

**Use vLLM (via vllm-delegator MCP tools) for:**
- Boilerplate code generation
...
```

### Problem: "Tool execution timeout"

Your vLLM might be slow. Try:
```python
# In mcp_vllm_delegator.py, increase timeout:
async with httpx.AsyncClient(timeout=120.0) as client:  # Was 60.0
```

---

## 📊 Performance Expectations

### Response Times (32B-AWQ on RTX 4090)

| Task | Expected Time | Quality |
|------|---------------|---------|
| Simple function | 2-4 seconds | Excellent |
| Boilerplate file | 3-6 seconds | Excellent |
| Test generation | 4-8 seconds | Very Good |
| Refactoring | 3-5 seconds | Good |
| Documentation | 2-4 seconds | Excellent |

### Response Times (7B on RTX 3070)

| Task | Expected Time | Quality |
|------|---------------|---------|
| Simple function | 1-2 seconds | Good |
| Boilerplate file | 2-3 seconds | Good |
| Test generation | 2-4 seconds | Fair |
| Refactoring | 2-3 seconds | Fair |
| Documentation | 1-2 seconds | Good |

---

## 🎓 Usage Patterns

### Pattern 1: Rapid Prototyping
```
You: "Create a basic REST API with these endpoints: list users, create user, delete user"

Claude will:
1. Use generate_boilerplate_file for each endpoint
2. Review and integrate them
3. Add error handling
4. Present complete, working code
```

### Pattern 2: Test-Driven Development
```
You: "I need a function to validate email addresses. Generate the tests first."

Claude will:
1. Use generate_tests for email validation scenarios
2. Review tests for completeness
3. Suggest additional edge cases
4. Then generate the implementation
```

### Pattern 3: Code Cleanup
```
You: "This file needs better documentation and style improvements"
[paste messy code]

Claude will:
1. Use generate_docstrings for documentation
2. Use improve_code_style for formatting
3. Review and suggest further improvements
4. Present cleaned code
```

### Pattern 4: Learning by Example
```
You: "Show me how to implement JWT authentication in FastAPI"

Claude will:
1. Use generate_simple_code for JWT setup
2. Add explanation of key concepts
3. Generate tests with generate_tests
4. Provide complete, educational example
```

---

## 💡 Pro Tips

### Tip 1: Be Specific About Delegation
```
❌ "Write some code for user management"
✅ "Generate a simple User CRUD class (delegate the boilerplate)"
```

### Tip 2: Request Reviews
```
"Generate tests for this function, but review them before showing me"
```
Claude will delegate, then improve the output.

### Tip 3: Batch Similar Tasks
```
"Generate Pydantic models for: User, Product, Order, and Review"
```
Claude can delegate all four at once for speed.

### Tip 4: Combine Tools
```
"Create a calculator module with tests and full documentation"
```
Claude will use multiple tools: generate_simple_code → generate_tests → generate_docstrings

### Tip 5: Iterate Quickly
```
First request: "Generate a basic API endpoint"
After review: "Add input validation"
After review: "Add error handling"
```

---

## 📈 Monitoring Usage

### Check vLLM Metrics
```bash
# Request count and performance
curl http://localhost:8002/metrics

# Watch real-time logs
podman logs -f vllm-qwen
```

### Track Tool Usage in Roo Code
Look for these in Claude's responses:
- "Generated with local LLM, reviewed and verified"
- Tool usage mentions in thinking process

### GPU Monitoring
```bash
# Real-time GPU usage
watch -n 1 nvidia-smi

# Or install nvtop for better visualization
sudo apt install nvtop
nvtop
```

---

## 🔄 Daily Workflow

### Morning Startup
```bash
# 1. Start vLLM (if not auto-starting)
podman start vllm-qwen

# 2. Verify it's ready
curl http://localhost:8002/v1/models

# 3. Open VS Code with Roo Code
code .
```

### During Development
- Let Claude decide what to delegate
- Request delegation explicitly for boilerplate
- Use for rapid iteration on simple tasks

### Evening Shutdown
```bash
# Optional: Stop container to free GPU memory
podman stop vllm-qwen
```

---

## 🎯 Next Steps

Once comfortable with basics:

1. **Customize Tools**: Add project-specific tools to the MCP server
2. **Tune Performance**: Adjust temperatures and max_tokens per tool
3. **Monitor Quality**: Track which delegations work best
4. **Scale Up**: Consider larger models for better quality
5. **Automate**: Create scripts for common delegation patterns

---

## 📚 Learning Resources

- **MCP Protocol**: https://modelcontextprotocol.io/docs
- **vLLM Docs**: https://docs.vllm.ai/
- **Qwen2.5-Coder**: https://qwenlm.github.io/blog/qwen2.5-coder/
- **Roo Code**: Check extension marketplace for tutorials

---

## 🆘 Getting Help

**Can't get it working?**

1. Run through the verification checklist above
2. Check troubleshooting section
3. Review vLLM logs: `podman logs vllm-qwen`
4. Test MCP server independently
5. Verify system prompt is correctly configured

**Still stuck?** Double-check:
- GPU has enough VRAM (20GB+ for 32B)
- Python 3.8+ is installed
- Port 8002 is not blocked by firewall
- File paths in config match your system

---

## ✨ Success Indicators

You'll know it's working when:
- ✅ Claude mentions "Generated with local LLM"
- ✅ Simple tasks complete in 2-5 seconds
- ✅ Code quality is consistent with your style
- ✅ You're not being prompted for simple boilerplate
- ✅ Development velocity increases noticeably

Happy delegating! 🚀