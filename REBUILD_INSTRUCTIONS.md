# Rebuild Instructions for Enhanced Logging

The enhanced logging changes require rebuilding the Docker container image to take effect.

## Quick Rebuild and Deploy

```bash
# Run the automated build and deploy script
./build-and-deploy.sh
```

This script will:
1. 🛑 Stop and remove the existing container
2. 🧹 Clean up the old image
3. 🔨 Build a new image with the latest code
4. 🚀 Start a new container with enhanced logging
5. 📋 Show the new logs with enhanced system information

## Manual Steps (if preferred)

### 1. Stop Current Container
```bash
podman stop vllm-delegator-mcp
podman rm vllm-delegator-mcp
```

### 2. Remove Old Image
```bash
podman rmi localhost/vllm-delegator-mcp:latest
```

### 3. Build New Image
```bash
podman build -f Dockerfile-vllm-delegator -t localhost/vllm-delegator-mcp:latest .
```

### 4. Start New Container
```bash
podman run -d \
    --name vllm-delegator-mcp \
    --network host \
    --env VLLM_API_URL="http://localhost:8002/v1/chat/completions" \
    --env VLLM_MODEL="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ" \
    --env LOGGING_ON="true" \
    --env LOG_LEVEL="INFO" \
    --env LOG_FILE="/app/logs/vllm_mcp_delegator.log" \
    --volume "$(pwd)/logs:/app/logs:Z" \
    --volume "$(pwd)/context_portal:/app/context_portal:Z" \
    --volume "$(pwd)/config.yaml:/app/config.yaml:Z" \
    --restart unless-stopped \
    --memory 2g \
    --cpus 2.0 \
    localhost/vllm-delegator-mcp:latest
```

## Verify Enhanced Logging

After rebuilding, you should see enhanced logs like:

```bash
# Check the new logs
podman logs vllm-delegator-mcp

# Or follow logs in real-time
podman logs -f vllm-delegator-mcp
```

**Expected enhanced log output:**
```
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - ======================================================================
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🚀 vLLM MCP Delegator Starting (Enhanced Version)
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 📅 Startup Time: 2025-10-14T18:50:22.367000
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 📊 Log Level: INFO
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 📁 Log File: /app/logs/vllm_mcp_delegator.log
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 💻 Platform: Linux-6.8.0-45-generic-x86_64-with-glibc2.39
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🐍 Python: 3.13.0
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - ⚙️  CPU Cores: 16
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🧠 Memory: 28.5GB available / 31.2GB total
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 💾 Disk Space: 145.3GB free
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🔢 Process ID: 12345
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 👤 User: vllm
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🌐 Hostname: container-hostname
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🤖 vLLM API URL: http://localhost:8002/v1/chat/completions
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🧠 vLLM Model: Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - ⏱️  vLLM Timeout: 180s
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - 🔧 Features - Caching: true, Metrics: true
2025-10-14 18:50:22,367 - utils.logging - INFO - [PID:12345] - ======================================================================
```

## Troubleshooting

### If Build Fails
```bash
# Check for syntax errors
python -m py_compile utils/logging.py
python -m py_compile vllm_delegator.py
python -m py_compile vllm_delegator_server.py

# Check dependencies
cat pyproject.toml | grep psutil
```

### If Container Won't Start
```bash
# Check container logs for errors
podman logs vllm-delegator-mcp

# Check if ports are available
ss -tlnp | grep 8002

# Check system resources
free -h
df -h
```

### If Still Seeing Old Logs
```bash
# Verify the new image was built
podman images | grep vllm-delegator-mcp

# Check the container is using the new image
podman inspect vllm-delegator-mcp | grep Image

# Force remove all related images and rebuild
podman rmi -f $(podman images | grep vllm-delegator | awk '{print $3}')
./build-and-deploy.sh
```

## Systemd Service Update

If you're using systemd service, restart it after rebuilding:

```bash
# Stop the service
sudo systemctl stop vllm-delegator-mcp.service

# Rebuild using the script
./build-and-deploy.sh

# The container should now be running with enhanced logging
# Check with journalctl
journalctl -u vllm-delegator-mcp.service -f
```

## Verification Checklist

- [ ] Container stops and removes cleanly
- [ ] New image builds without errors
- [ ] Container starts successfully
- [ ] Enhanced logs show system information (CPU, memory, etc.)
- [ ] Logs include emoji icons and structured formatting
- [ ] vLLM connection status is clearly indicated
- [ ] Process ID is included in log format
- [ ] Performance metrics are logged for tool executions

Once rebuilt, the enhanced logging system will provide much more detailed and visually organized system information!
