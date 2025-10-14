#!/usr/bin/env python3
"""
vLLM Delegator MCP Server Launcher
A simple server script to run the vLLM delegator MCP service.
"""

import asyncio
import importlib.util
import logging
import os
import sys
from pathlib import Path

# Add the current directory to Python path to import our delegator
current_dir = Path(__file__).resolve().parent
print("🚀 Starting vLLM Delegator MCP Server")
print(f"📁 Current directory: {current_dir}")

# Ensure current_dir is on sys.path once, at the front
current_dir_str = str(current_dir)
if current_dir_str not in sys.path:
    sys.path.insert(0, current_dir_str)

# Robust import with detailed diagnostics
delegator_main = None
try:
    from vllm_delegator import main as delegator_main

    print("✅ Successfully imported vllm_delegator.main")
except ImportError as e:
    print("❌ Error: Could not import vllm_delegator.py")
    print(f"📁 Current directory: {current_dir}")
    print(f"🐍 sys.path (first 5): {sys.path[:5]}")
    print(f"💥 Import error details: {e}")

    # Probe directly by file path for clearer error messages
    candidate = current_dir / "vllm_delegator.py"
    print(f"🔍 Looking for: {candidate}")

    if candidate.exists():
        print("📄 File exists but import failed. Attempting direct load...")
        try:
            spec = importlib.util.spec_from_file_location("vllm_delegator", candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules["vllm_delegator"] = mod
                spec.loader.exec_module(mod)
                delegator_main = getattr(mod, "main", None)
                if delegator_main is None:
                    print("❌ Error: Found vllm_delegator.py but no 'main' function.")
                    sys.exit(1)
                print("✅ Successfully loaded vllm_delegator.py directly")
            else:
                print("❌ Error: Could not create module spec")
                sys.exit(1)
        except Exception as inner:
            print("❌ Error: Found vllm_delegator.py but loading failed:")
            print(f"  💥 {type(inner).__name__}: {inner}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
    else:
        print(
            "❌ Error: vllm_delegator.py not found in the same directory as this script"
        )
        print(f"📂 Directory contents: {list(current_dir.iterdir())[:10]}")
        sys.exit(1)


def setup_logging():
    """Setup basic logging for the server launcher"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logger = logging.getLogger(__name__)
    logger.info("🔧 Server launcher logging initialized")
    return logger


def check_environment():
    """Check if required environment variables are set"""
    logger = logging.getLogger(__name__)

    required_vars = []
    optional_vars = {
        "VLLM_API_URL": "http://localhost:8002/v1/chat/completions",
        "VLLM_MODEL": "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
        "LOGGING_ON": "true",
        "LOG_LEVEL": "INFO",
        "LOG_FILE": "/tmp/vllm_mcp_delegator.log",
    }

    # Check for missing required variables
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(
            f"❌ Missing required environment variables: {', '.join(missing_vars)}"
        )
        return False

    # Set default values for optional variables
    for var, default in optional_vars.items():
        if not os.getenv(var):
            os.environ[var] = default
            logger.info(f"⚙️  Using default value for {var}: {default}")
        else:
            logger.info(f"⚙️  Using configured value for {var}: {os.getenv(var)}")

    return True


def check_vllm_connection():
    """Check if vLLM server is accessible (optional check)"""
    logger = logging.getLogger(__name__)

    try:
        import httpx
    except ImportError:
        logger.warning("⚠️  httpx not installed, skipping vLLM connection check")
        return False

    vllm_url = os.getenv("VLLM_API_URL", "http://localhost:8002/v1/chat/completions")
    models_url = vllm_url.replace("/chat/completions", "/models")

    try:
        with httpx.Client(timeout=5.0) as client:
            logger.info(f"🔗 Testing connection to vLLM at {models_url}")
            response = client.get(models_url)
            if response.status_code == 200:
                logger.info(f"✅ vLLM server is accessible at {vllm_url}")
                return True
            else:
                logger.warning(
                    f"⚠️  vLLM server responded with status {response.status_code}"
                )
                return False
    except Exception as e:
        logger.error(f"❌ Cannot connect to vLLM server at {vllm_url}: {e}")
        logger.warning(
            "⚠️  The server will start anyway, but tools will fail until vLLM is available"
        )
        return False


def display_startup_info():
    """Display startup information"""
    logger = logging.getLogger(__name__)

    print("=" * 60)
    print("🤖 vLLM Delegator MCP Server")
    print("=" * 60)

    logger.info("📋 Configuration Summary:")
    logger.info(f"  🤖 vLLM API URL: {os.getenv('VLLM_API_URL')}")
    logger.info(f"  🧠 vLLM Model: {os.getenv('VLLM_MODEL')}")
    logger.info(f"  📊 Logging: {os.getenv('LOGGING_ON')}")
    logger.info(f"  📈 Log Level: {os.getenv('LOG_LEVEL')}")
    logger.info(f"  📁 Log File: {os.getenv('LOG_FILE')}")

    # Check for config file
    config_file = os.getenv("CONFIG_FILE", "config.yaml")
    if os.path.exists(config_file):
        logger.info(f"  ⚙️  Config File: {config_file} (found)")
    else:
        logger.info(
            f"  ⚙️  Config File: {config_file} (not found, using environment variables)"
        )

    print("\n🚀 Starting server...")
    print("-" * 60)


def main():
    """Main entry point"""
    logger = setup_logging()
    logger.info("🚀 vLLM Delegator MCP Server Launcher starting")

    # Check environment setup
    if not check_environment():
        logger.error("❌ Environment check failed")
        sys.exit(1)

    # Optional vLLM connection check
    vllm_available = check_vllm_connection()
    if vllm_available:
        logger.info("✅ vLLM connection verified")
    else:
        logger.warning("⚠️  vLLM connection not available")

    # Display configuration
    display_startup_info()

    # Run the server
    try:
        if delegator_main is None:
            logger.error("❌ delegator_main is None - import failed")
            sys.exit(1)

        logger.info("🎯 Delegating to main vLLM delegator service")
        asyncio.run(delegator_main())
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user (Ctrl+C)")
        print("\n🛑 Shutdown complete")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
        print(f"💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
