"""
Logging utilities and setup with enhanced system information
"""

import logging
import os
import platform
import sys
from datetime import datetime

try:
    import psutil  # type: ignore[import-untyped]
except ImportError:
    psutil = None  # psutil is optional for enhanced system info


def get_system_info():
    """Get system information for logging"""
    try:
        info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "pid": os.getpid(),
            "user": os.getenv("USER", "unknown"),
            "hostname": platform.node(),
        }

        if psutil:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            info.update(
                {
                    "cpu_count": psutil.cpu_count(),
                    "memory_total_gb": round(memory.total / (1024**3), 2),
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                    "disk_free_gb": round(disk.free / (1024**3), 2),
                }
            )

        return info
    except Exception as e:
        return {"error": f"Failed to get system info: {e}"}


def setup_logging(config=None):
    """Setup logging based on configuration with enhanced system information"""

    if config and config.logging and config.logging.enabled:
        log_dir = os.path.dirname(config.logging.file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Enhanced format with more context
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s"
        )

        logging.basicConfig(
            level=getattr(logging, config.logging.level, logging.INFO),
            format=log_format,
            handlers=[
                logging.FileHandler(config.logging.file),
                logging.StreamHandler(sys.stderr),
            ],
        )
        logger = logging.getLogger(__name__)

        # Enhanced startup logging with system information
        logger.info("=" * 70)
        logger.info("🚀 vLLM MCP Delegator Starting (Enhanced Version)")
        logger.info(f"📅 Startup Time: {datetime.now().isoformat()}")
        logger.info(f"📊 Log Level: {config.logging.level}")
        logger.info(f"📁 Log File: {config.logging.file}")

        # System information
        sys_info = get_system_info()
        if "error" not in sys_info:
            logger.info(f"💻 Platform: {sys_info['platform']}")
            logger.info(f"🐍 Python: {sys_info['python_version']}")
            if "cpu_count" in sys_info:
                logger.info(f"⚙️  CPU Cores: {sys_info['cpu_count']}")
                logger.info(
                    f"🧠 Memory: {sys_info['memory_available_gb']:.1f}GB available / {sys_info['memory_total_gb']:.1f}GB total"
                )
                logger.info(f"💾 Disk Space: {sys_info['disk_free_gb']:.1f}GB free")
            logger.info(f"🔢 Process ID: {sys_info['pid']}")
            logger.info(f"👤 User: {sys_info['user']}")
            logger.info(f"🌐 Hostname: {sys_info['hostname']}")
        else:
            logger.warning(f"⚠️  System Info: {sys_info['error']}")

        # Configuration details
        if hasattr(config, "vllm") and config.vllm:
            logger.info(f"🤖 vLLM API URL: {config.vllm.api_url}")
            logger.info(f"🧠 vLLM Model: {config.vllm.model}")
            if hasattr(config.vllm, "timeout"):
                logger.info(f"⏱️  vLLM Timeout: {config.vllm.timeout}s")

        if hasattr(config, "features") and config.features:
            logger.info(
                f"🔧 Features - Caching: {config.features.caching}, Metrics: {config.features.metrics}"
            )
            if hasattr(config.features, "auto_backup"):
                logger.info(f"🔧 Auto-backup: {config.features.auto_backup}")

        if (
            hasattr(config, "security")
            and config.security
            and hasattr(config.security, "allowed_paths")
            and config.security.allowed_paths
        ):
            logger.info(
                f"🔒 Security: {len(config.security.allowed_paths)} allowed paths configured"
            )

        logger.info("=" * 70)
    else:
        logging.basicConfig(
            level=logging.ERROR,
            format="%(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )

    return logging.getLogger(__name__)


def log_info(msg, config=None):
    """Log info message if logging is enabled"""
    if (
        config
        and hasattr(config, "logging")
        and config.logging
        and config.logging.enabled
    ):
        logging.getLogger(__name__).info(msg)


def log_debug(msg, config=None):
    """Log debug message if logging is enabled"""
    if (
        config
        and hasattr(config, "logging")
        and config.logging
        and config.logging.enabled
    ):
        logging.getLogger(__name__).debug(msg)


def log_error(msg, exc_info=False):
    """Log error message (always enabled)"""
    logging.getLogger(__name__).error(msg, exc_info=exc_info)


def log_tool_execution(tool_name, start_time, success, duration=None, details=None):
    """Log tool execution with performance metrics"""
    logger = logging.getLogger(__name__)
    status = "✅ SUCCESS" if success else "❌ FAILED"
    duration_str = f" ({duration:.3f}s)" if duration else ""
    details_str = f" - {details}" if details else ""
    logger.info(f"🔧 Tool: {tool_name} - {status}{duration_str}{details_str}")


def log_vllm_request(
    model, prompt_length, response_length=None, duration=None, success=True
):
    """Log vLLM API requests with metrics"""
    logger = logging.getLogger(__name__)
    status = "✅" if success else "❌"
    duration_str = f" ({duration:.3f}s)" if duration else ""
    response_str = f" -> {response_length} chars" if response_length else ""
    logger.info(
        f"🤖 vLLM {status}: {model} - {prompt_length} chars{response_str}{duration_str}"
    )


def log_system_event(event_type, message, details=None):
    """Log system events with categorization"""
    logger = logging.getLogger(__name__)
    icons = {
        "startup": "🚀",
        "shutdown": "🛑",
        "connection": "🔗",
        "error": "💥",
        "warning": "⚠️",
        "config": "⚙️",
        "security": "🔒",
        "performance": "📊",
    }
    icon = icons.get(event_type, "📝")
    details_str = f" - {details}" if details else ""
    logger.info(f"{icon} {event_type.upper()}: {message}{details_str}")


def log_memory_usage():
    """Log current memory usage"""
    if not psutil:
        return

    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        logger = logging.getLogger(__name__)
        logger.debug(f"🧠 Memory Usage: {memory_mb:.1f}MB RSS")
    except Exception as e:
        log_error(f"Failed to get memory usage: {e}")
