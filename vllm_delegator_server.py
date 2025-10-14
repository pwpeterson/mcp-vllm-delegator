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
print(f"Current directory: {current_dir}")

# Ensure current_dir is on sys.path once, at the front
current_dir_str = str(current_dir)
if current_dir_str not in sys.path:
    sys.path.insert(0, current_dir_str)

# Robust import with detailed diagnostics
try:
    from vllm_delegator import main as delegator_main
except ImportError as e:
    print("Error: Could not import vllm_delegator.py")
    print(f"Current directory: {current_dir}")
    print(f"sys.path (first 5): {sys.path[:5]}")
    print(f"Import error details: {e}")

    # Probe directly by file path for clearer error messages
    candidate = current_dir / "vllm_delegator.py"
    print(f"Looking for: {candidate}")

    if candidate.exists():
        print("File exists but import failed. Attempting direct load...")
        try:
            spec = importlib.util.spec_from_file_location("vllm_delegator", candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules["vllm_delegator"] = mod
                spec.loader.exec_module(mod)
                delegator_main = getattr(mod, "main", None)
                if delegator_main is None:
                    print("Error: Found vllm_delegator.py but no 'main' function.")
                    sys.exit(1)
                print("✓ Successfully loaded vllm_delegator.py directly")
            else:
                print("Error: Could not create module spec")
                sys.exit(1)
        except Exception as inner:
            print("Error: Found vllm_delegator.py but loading failed:")
            print(f"  {type(inner).__name__}: {inner}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
    else:
        print("Error: vllm_delegator.py not found in the same directory as this script")
        print(f"Directory contents: {list(current_dir.iterdir())[:10]}")
        sys.exit(1)


def setup_logging():
    """Setup basic logging for the server launcher"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def check_environment():
    """Check if required environment variables are set"""
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
        print(
            f"Error: Missing required environment variables: {', '.join(missing_vars)}"
        )
        return False

    # Set default values for optional variables
    for var, default in optional_vars.items():
        if not os.getenv(var):
            os.environ[var] = default
            print(f"Using default value for {var}: {default}")

    return True


def check_vllm_connection():
    """Check if vLLM server is accessible (optional check)"""
    try:
        import httpx
    except ImportError:
        print("⚠ httpx not installed, skipping vLLM connection check")
        return False

    vllm_url = os.getenv("VLLM_API_URL", "http://localhost:8002/v1/chat/completions")
    models_url = vllm_url.replace("/chat/completions", "/models")

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(models_url)
            if response.status_code == 200:
                print(f"✓ vLLM server is accessible at {vllm_url}")
                return True
            else:
                print(f"⚠ vLLM server responded with status {response.status_code}")
                return False
    except Exception as e:
        print(f"⚠ Cannot connect to vLLM server at {vllm_url}: {e}")
        print(
            "The server will start anyway, but tools will fail until vLLM is available"
        )
        return False


async def run_server():
    """Run the vLLM delegator MCP server"""
    print("Starting vLLM Delegator MCP Server...")
    print("Press Ctrl+C to stop the server")

    try:
        await delegator_main()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        print(f"Server encountered an error: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    setup_logging()

    print("=" * 60)
    print("vLLM Delegator MCP Server")
    print("=" * 60)

    # Check environment setup
    if not check_environment():
        sys.exit(1)

    # Optional vLLM connection check
    check_vllm_connection()

    # Display configuration
    print("\nConfiguration:")
    print(f"  vLLM API URL: {os.getenv('VLLM_API_URL')}")
    print(f"  vLLM Model: {os.getenv('VLLM_MODEL')}")
    print(f"  Logging: {os.getenv('LOGGING_ON')}")
    print(f"  Log Level: {os.getenv('LOG_LEVEL')}")
    print(f"  Log File: {os.getenv('LOG_FILE')}")

    # Check for config file
    config_file = os.getenv("CONFIG_FILE", "config.yaml")
    if os.path.exists(config_file):
        print(f"  Config File: {config_file} (found)")
    else:
        print(f"  Config File: {config_file} (not found, using environment variables)")

    print("\nStarting server...")
    print("-" * 60)

    # Run the server
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
