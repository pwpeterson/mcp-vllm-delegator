#!/usr/bin/env python3
import asyncio
import httpx

VLLM_API_URL = "http://localhost:8002/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"

async def test_generate_code():
    """Test the generate_simple_code functionality"""
    prompt = """You are a code generator. Generate clean, working python code for the following request.
Only output the code, no explanations unless asked.

Request: Create a function to calculate fibonacci numbers"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(VLLM_API_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.2
        })
        
        result = response.json()
        code = result['choices'][0]['message']['content']
        print("Generated Code:")
        print("=" * 50)
        print(code)
        print("=" * 50)
        print(f"Success! Generated {len(code)} characters")

if __name__ == "__main__":
    asyncio.run(test_generate_code())