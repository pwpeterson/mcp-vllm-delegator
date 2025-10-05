#!/usr/bin/env python3
import asyncio
import httpx

async def test_vllm():
    """Direct test of vLLM without MCP"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test 1: Check models endpoint
            print("Testing vLLM models endpoint...")
            response = await client.get("http://localhost:8002/v1/models")
            print(f"✓ Models endpoint: {response.status_code}")
            print(f"Response: {response.json()}\n")
            
            # Test 2: Generate simple code
            print("Testing code generation...")
            response = await client.post(
                "http://localhost:8002/v1/chat/completions",
                json={
                    "model": "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
                    "messages": [{"role": "user", "content": "Write a hello world function in Python"}],
                    "max_tokens": 200,
                    "temperature": 0.2
                }
            )
            print(f"✓ Generation endpoint: {response.status_code}")
            result = response.json()
            code = result['choices'][0]['message']['content']
            print(f"Generated code:\n{code}\n")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_vllm())