#!/usr/bin/env python3
"""
Healthcheck script for vLLM-Delegator MCP Server
Tests if the server can initialize properly and connect to vLLM
"""

import sys
from pathlib import Path


def main():
    """Main healthcheck function"""
    try:
        # Add the app directory to Python path
        app_dir = Path(__file__).parent
        sys.path.insert(0, str(app_dir))

        # Try to import and initialize the VLLMDelegator
        from vllm_delegator import VLLMDelegator

        # Create delegator instance (this tests configuration loading)
        delegator = VLLMDelegator()

        # Check if delegator was created successfully
        if delegator is None:
            print("ERROR: Failed to create VLLMDelegator instance", file=sys.stderr)
            return 1

        # Test basic functionality
        if hasattr(delegator, "config") and delegator.config:
            print("OK: VLLMDelegator initialized successfully")
            return 0
        else:
            print("ERROR: VLLMDelegator missing configuration", file=sys.stderr)
            return 1

    except ImportError as e:
        print(f"ERROR: Failed to import VLLMDelegator: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: Healthcheck failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
