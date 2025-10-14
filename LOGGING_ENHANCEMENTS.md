# vLLM Delegator MCP - Enhanced Logging

## Overview

The logging system has been significantly enhanced to provide comprehensive system monitoring, performance tracking, and debugging capabilities.

## Key Improvements

### 1. Enhanced System Information Logging

**New startup information includes:**
- 🚀 Enhanced startup banner with emojis for better visibility
- 💻 Platform and system details (OS, Python version, hostname)
- 🧠 Memory usage (available/total GB)
- 💾 Disk space information
- ⚙️ CPU core count
- 🔢 Process ID and user information
- 🌐 Hostname for multi-server environments

### 2. Categorized Event Logging

**New event types with icons:**
- 🚀 `startup` - Server initialization events
- 🛑 `shutdown` - Graceful shutdown events
- 🔗 `connection` - vLLM connection status
- 💥 `error` - Error conditions
- ⚠️ `warning` - Warning conditions
- ⚙️ `config` - Configuration details
- 🔒 `security` - Security-related events
- 📊 `performance` - Performance metrics

### 3. Performance Monitoring

**Tool execution tracking:**
- ✅/❌ Success/failure status with duration
- 🔧 Tool name and execution details
- 📊 Performance metrics collection

**vLLM API call monitoring:**
- 🤖 Request/response size tracking
- ⏱️ API call duration measurement
- 🔄 Retry attempt logging with backoff details
- 💾 Cache hit/miss tracking

### 4. Enhanced Error Handling

**Improved error reporting:**
- Exception type classification
- Stack trace preservation for debugging
- Retry logic with detailed failure reasons
- Connection failure categorization

### 5. Configuration Visibility

**Startup configuration display:**
- 🤖 vLLM API URL and model information
- 🔧 Feature flags (caching, metrics, auto-backup)
- 🔒 Security settings (allowed paths count)
- 📁 Log file location and level

## New Logging Functions

### `log_system_event(event_type, message, details=None)`
Categorized system event logging with icons and structured format.

### `log_tool_execution(tool_name, start_time, success, duration=None, details=None)`
Tool execution tracking with performance metrics.

### `log_vllm_request(model, prompt_length, response_length=None, duration=None, success=True)`
vLLM API request logging with comprehensive metrics.

### `log_memory_usage()`
Memory usage monitoring (requires psutil).

## Enhanced Log Format

**New format includes:**
```
%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s
```

**Benefits:**
- Process ID for multi-process debugging
- Consistent timestamp format
- Clear level indication
- Structured message format

## Dependencies Added

- `psutil>=5.9.0` - System information gathering (optional, graceful fallback)

## Sample Enhanced Log Output

```
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - ======================================================================
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🚀 vLLM MCP Delegator Starting (Enhanced Version)
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 📅 Startup Time: 2025-10-14T18:41:22.367000
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 📊 Log Level: INFO
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 📁 Log File: /app/logs/vllm_mcp_delegator.log
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 💻 Platform: Linux-6.8.0-45-generic-x86_64-with-glibc2.39
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🐍 Python: 3.13.0
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - ⚙️  CPU Cores: 16
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🧠 Memory: 28.5GB available / 31.2GB total
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 💾 Disk Space: 145.3GB free
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🔢 Process ID: 1180394
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 👤 User: vllm
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🌐 Hostname: thx1138ai
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🤖 vLLM API URL: http://localhost:8002/v1/chat/completions
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🧠 vLLM Model: Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - ⏱️  vLLM Timeout: 180s
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🔧 Features - Caching: true, Metrics: true, Auto-backup: false
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - 🔒 Security: 3 allowed paths configured
2025-10-14 18:41:22,367 - utils.logging - INFO - [PID:1180394] - ======================================================================
2025-10-14 18:41:22,368 - utils.logging - INFO - [PID:1180394] - ⚙️ CONFIG: vLLM Configuration - URL: http://localhost:8002/v1/chat/completions, Model: Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
2025-10-14 18:41:22,368 - utils.logging - INFO - [PID:1180394] - 🔒 SECURITY: Security Configuration - Allowed paths: 3
2025-10-14 18:41:22,368 - utils.logging - INFO - [PID:1180394] - ⚙️ CONFIG: Feature Configuration - Caching=true, Metrics=true
2025-10-14 18:41:22,368 - utils.logging - INFO - [PID:1180394] - 🚀 STARTUP: Tools enumeration requested
2025-10-14 18:41:22,368 - utils.logging - INFO - [PID:1180394] - 🚀 STARTUP: Tools enumeration complete - 40 tools available
2025-10-14 18:41:22,368 - utils.logging - INFO - [PID:1180394] - 🚀 STARTUP: Enhanced MCP server initialization started
2025-10-14 18:41:22,368 - utils.logging - INFO - [PID:1180394] - 🔗 CONNECTION: Testing vLLM connection
2025-10-14 18:41:22,400 - utils.logging - INFO - [PID:1180394] - 🔗 CONNECTION: vLLM connection established - Status: 200
2025-10-14 18:41:22,400 - utils.logging - INFO - [PID:1180394] - 🚀 STARTUP: Starting stdio server interface
2025-10-14 18:41:22,400 - utils.logging - INFO - [PID:1180394] - 🚀 STARTUP: Enhanced MCP server ready and listening - vLLM: connected
```

## Benefits

1. **Better Debugging** - Clear categorization and detailed context
2. **Performance Monitoring** - Track API calls, tool execution, and system resources
3. **Operational Visibility** - Easy identification of issues in production
4. **System Health** - Monitor memory, disk, and connection status
5. **Visual Clarity** - Emoji icons for quick log scanning
6. **Structured Data** - Consistent format for log parsing tools

## Backward Compatibility

All existing logging functions remain unchanged. New functions are additive and optional.
