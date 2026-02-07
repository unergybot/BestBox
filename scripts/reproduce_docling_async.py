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
    
    with open("test.txt", "w") as f:
        f.write("test content")
        
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Test Sync (Confirmed 404)
        print("\n1. Testing Sync /v1/convert/file ...")
        files = {'files': ('test.txt', open('test.txt', 'rb'), 'text/plain')}
        # data = {'to_formats': 'md'}
        try:
            resp = await client.post(f"{url}/v1/convert/file", files=files)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

        # 2. Test Async /v1/convert/file/async
        print("\n2. Testing Async /v1/convert/file/async ...")
        failed_async = False
        task_id = None
        try:
            # Re-open file because previous read exhausted it
            files = {'files': ('test.txt', open('test.txt', 'rb'), 'text/plain')}
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
            try:
                resp = await client.get(f"{url}/v1/status/poll/{task_id}")
                print(f"Poll Status: {resp.status_code}")
                print(f"Poll Body: {resp.text}")
            except Exception as e:
                print(f"Poll Error: {e}")

    if os.path.exists("test.txt"):
        os.remove("test.txt")

if __name__ == "__main__":
    asyncio.run(main())
