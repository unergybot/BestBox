import asyncio
import os
import sys
import httpx
import json

# Ensure we can import from services
sys.path.append(os.getcwd())

from services.docling_client import DoclingClient

async def main():
    url = "http://127.0.0.1:5001"
    print(f"--- Testing URL: {url} ---")
    
    if not os.path.exists("test.png"):
        print("Error: test.png not found")
        return
        
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test Async /v1/convert/file/async with PNG
        print("\n2. Testing Async /v1/convert/file/async with PNG ...")
        failed_async = False
        task_id = None
        try:
            files = {'files': ('test.png', open('test.png', 'rb'), 'image/png')}
            resp = await client.post(f"{url}/v1/convert/file/async", files=files)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
            if resp.status_code == 200:
                task_id = resp.json().get('task_id')
                print(f"Task ID: {task_id}")
        except Exception as e:
            print(f"Error: {e}")
            failed_async = True

        # 3. Poll if async started
        if task_id:
            print(f"\n3. Polling Task {task_id} ...")
            for i in range(5):
                try:
                    resp = await client.get(f"{url}/v1/status/poll/{task_id}")
                    print(f"Poll {i}: {resp.status_code} - {resp.text}")
                    data = resp.json()
                    if data.get("task_status") in ["success", "completed", "failure"]:
                        break
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Poll Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
