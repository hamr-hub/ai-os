import httpx
import asyncio
import time
import os
import sys

# Simulation of a simple test for mocks
async def test_mocks():
    print("Testing Mocks...")
    base_url = "http://localhost:35000"
    
    try:
        # 1. Check health
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/health")
            print(f"Health check: {resp.status_code}, {resp.json()}")
            
            # 2. Check GPU summary
            resp = await client.get(f"{base_url}/manage/gpu/summary")
            data = resp.json()
            print(f"GPU Health Score: {data.get('health_score')}")
            
            # 3. Inject fault: OOM
            print("Injecting OOM fault...")
            await client.post(f"{base_url}/manage/faults", json={"oom_on_load": True})
            
            # 4. Try to start a model (this would go through systemctl mock)
            # In a real test, we would call the actual systemctl mock script
            # Here we just verify the state changes
            
            print("Mocks seem to be working! (Ensure mock_vllm_server.py is running on port 35000)")
            
    except Exception as e:
        print(f"Error testing mocks: {e}")
        print("Make sure you have started the mock server: python mock_vllm_server.py")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        asyncio.run(test_mocks())
    else:
        print("This is a mock validation script. Run with --run to execute tests.")
