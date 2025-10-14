# vLLM-Delegator Deployment Guide

Complete guide for deploying the vLLM-Delegator MCP Server using Podman containers.

## Prerequisites

### System Requirements
- **OS**: Linux (RHEL/CentOS/Fedora/Ubuntu)
- **RAM**: Minimum 4GB, Recommended 8GB+
- **CPU**: 2+ cores
- **Storage**: 2GB free space
- **Network**: Access to vLLM server (default: port 8002)

### Software Dependencies
```bash
# Install Podman (RHEL/CentOS/Fedora)
sudo dnf install podman podman-compose

# Install Podman (Ubuntu/Debian)
sudo apt update
sudo apt install podman podman-compose

# Verify installation
podman --version
podman-compose --version
```

### vLLM Server Setup
Ensure your vLLM server is running with Qwen2.5-Coder-32B-Instruct-AWQ:
```bash
# Example vLLM server command
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
    --host 0.0.0.0 \
    --port 8002 \
    --api-key your-api-key
```

## Quick Start

### 1. Clone and Setup
```bash
cd /path/to/mcp-vllm-delegator

# Ensure all files are present
ls -la Dockerfile podman-run.sh docker-compose.yml

# Make script executable (if not already)
chmod +x podman-run.sh
```

### 2. Build and Run
```bash
# Build the container image
./podman-run.sh build

# Create and start the container
./podman-run.sh run

# Check status
./podman-run.sh status
```

### 3. Verify Deployment
```bash
# Check container logs
./podman-run.sh logs

# Should see output like:
# [INFO] vLLM-Delegator MCP Server starting...
# [INFO] Connected to vLLM server at http://host.containers.internal:8002
# [INFO] Server listening on stdio
```

## Configuration

### Environment Variables
Edit `config.yaml` or set environment variables:

```yaml
# config.yaml
vllm:
  api_url: "http://host.containers.internal:8002/v1/chat/completions"
  model: "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
  api_key: "your-api-key"  # Optional
  timeout: 120
  max_retries: 3

logging:
  level: "INFO"
  file: "/app/logs/vllm_mcp_delegator.log"
  enabled: true

server:
  max_workers: 4
  request_timeout: 300
```

### Network Configuration
The container uses `--network host` to access the host's vLLM server. If your vLLM server is on a different host:

```bash
# Edit podman-run.sh and change:
VLLM_API_URL="http://your-vllm-server:8002/v1/chat/completions"
```

## Management Commands

### Container Lifecycle
```bash
# Build image
./podman-run.sh build

# Create and start container
./podman-run.sh run

# Start existing container
./podman-run.sh start

# Stop container
./podman-run.sh stop

# Restart container
./podman-run.sh restart

# Remove container
./podman-run.sh remove

# Update (rebuild and restart)
./podman-run.sh update
```

### Monitoring
```bash
# Check status and resource usage
./podman-run.sh status

# Follow logs in real-time
./podman-run.sh logs

# Enter container shell for debugging
./podman-run.sh shell

# Check health status
podman inspect vllm-delegator-mcp --format '{{.State.Health.Status}}'
```

## Production Deployment

### Systemd Service (Rootless)
For production deployment with automatic startup:

```bash
# Copy service file to user systemd directory
mkdir -p ~/.config/systemd/user
cp vllm-delegator.service ~/.config/systemd/user/

# Enable and start service
systemctl --user daemon-reload
systemctl --user enable vllm-delegator.service
systemctl --user start vllm-delegator.service

# Check service status
systemctl --user status vllm-delegator.service

# Enable lingering (service starts on boot)
sudo loginctl enable-linger $USER
```

### Docker Compose Alternative
```bash
# Using docker-compose (if preferred)
podman-compose -f docker-compose.yml up -d

# Check status
podman-compose -f docker-compose.yml ps

# View logs
podman-compose -f docker-compose.yml logs -f

# Stop services
podman-compose -f docker-compose.yml down
```

## Security Considerations

### Container Security
- **Non-root user**: Container runs as `mcpuser` (UID 1000)
- **Read-only filesystem**: Prevents runtime modifications
- **Dropped capabilities**: All Linux capabilities dropped
- **No new privileges**: Prevents privilege escalation
- **Resource limits**: Memory and CPU limits enforced
- **Tmpfs mounts**: Temporary files in memory

### Network Security
```bash
# If using custom network instead of host networking:
podman network create vllm-network

# Run with custom network (modify podman-run.sh):
--network vllm-network \
--publish 8003:8003 \
```

### SELinux Compatibility
The container is configured with SELinux labels (`Z` flag on volumes):
```bash
# Check SELinux context
ls -Z logs/ context_portal/

# If SELinux issues occur:
sudo setsebool -P container_manage_cgroup on
```

## Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check Podman status
podman info

# Check system resources
free -h
df -h

# Check for port conflicts
ss -tlnp | grep 8002
```

#### vLLM Connection Issues
```bash
# Test vLLM server connectivity from container
podman exec vllm-delegator-mcp curl -f http://host.containers.internal:8002/health

# Check vLLM server logs
# (on vLLM server host)
tail -f /path/to/vllm/logs
```

#### Permission Issues
```bash
# Fix log directory permissions
sudo chown -R $USER:$USER logs/ context_portal/
chmod 755 logs/ context_portal/
```

#### Memory Issues
```bash
# Check container memory usage
podman stats vllm-delegator-mcp

# Increase memory limit in podman-run.sh:
--memory 4g \
```

### Debug Mode
```bash
# Run container in debug mode
podman run -it --rm \
    --env LOG_LEVEL=DEBUG \
    --volume $(pwd)/logs:/app/logs:Z \
    vllm-delegator:latest /bin/bash

# Inside container:
python vllm_delegator_server.py
```

### Log Analysis
```bash
# Check application logs
tail -f logs/vllm_mcp_delegator.log

# Check container logs
podman logs vllm-delegator-mcp

# Check systemd service logs (if using systemd)
journalctl --user -u vllm-delegator.service -f
```

## Performance Tuning

### Resource Optimization
```bash
# Adjust CPU limits in podman-run.sh:
--cpus 4.0 \  # Use 4 CPU cores

# Adjust memory limits:
--memory 4g \  # Use 4GB RAM

# Adjust worker processes in config.yaml:
server:
  max_workers: 8  # Increase for higher concurrency
```

### Monitoring Setup
```bash
# Install monitoring tools
sudo dnf install htop iotop nethogs

# Monitor container resources
watch -n 1 'podman stats vllm-delegator-mcp'

# Monitor system resources
htop
```

## Backup and Recovery

### Backup Configuration
```bash
# Backup configuration and data
tar -czf vllm-delegator-backup-$(date +%Y%m%d).tar.gz \
    config.yaml \
    logs/ \
    context_portal/ \
    Dockerfile \
    podman-run.sh
```

### Disaster Recovery
```bash
# Stop and remove container
./podman-run.sh remove

# Restore from backup
tar -xzf vllm-delegator-backup-YYYYMMDD.tar.gz

# Rebuild and restart
./podman-run.sh build
./podman-run.sh run
```

## Integration with MCP Clients

### Claude Desktop Integration
Add to Claude Desktop configuration:
```json
{
  "mcpServers": {
    "vllm-delegator": {
      "command": "podman",
      "args": [
        "exec", "-i", "vllm-delegator-mcp",
        "python", "/app/vllm_delegator_server.py"
      ]
    }
  }
}
```

### Custom MCP Client
```python
# Example Python client
import subprocess
import json

def call_vllm_delegator(tool_name, args):
    cmd = [
        "podman", "exec", "-i", "vllm-delegator-mcp",
        "python", "/app/vllm_delegator_server.py"
    ]

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": args
        }
    }

    result = subprocess.run(
        cmd,
        input=json.dumps(request),
        text=True,
        capture_output=True
    )

    return json.loads(result.stdout)
```

## Support and Maintenance

### Regular Maintenance
```bash
# Weekly maintenance script
#!/bin/bash
# weekly-maintenance.sh

# Update container
./podman-run.sh update

# Clean up old images
podman image prune -f

# Rotate logs
find logs/ -name "*.log" -mtime +30 -delete

# Check disk space
df -h
```

### Health Checks

The container includes comprehensive health checks that test actual MCP server functionality:

```bash
# Check container health status
podman inspect vllm-delegator-mcp --format '{{.State.Health.Status}}'

# Manual health check using included script
podman exec vllm-delegator-mcp python /app/healthcheck.py

# Create automated health monitoring script
#!/bin/bash
# health-monitor.sh

HEALTH_STATUS=$(podman inspect vllm-delegator-mcp --format '{{.State.Health.Status}}' 2>/dev/null)

if [ "$HEALTH_STATUS" != "healthy" ]; then
    echo "Container unhealthy (status: $HEALTH_STATUS), restarting..."
    ./podman-run.sh restart
else
    echo "Container healthy"
fi

# Add to crontab for automated monitoring
# */5 * * * * /path/to/health-monitor.sh
```

**Health Check Details:**
- **Test**: Imports and initializes VLLMDelegator class
- **Frequency**: Every 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3 attempts before marking unhealthy
- **Start Period**: 10 seconds grace period on startup

## Conclusion

The vLLM-Delegator is now ready for production deployment with:
- ✅ Secure containerized environment
- ✅ Automated management scripts
- ✅ Systemd service integration
- ✅ Comprehensive monitoring
- ✅ Security hardening
- ✅ Resource management

For additional support or advanced configurations, refer to the project documentation or create an issue in the repository.
