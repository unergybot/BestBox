import asyncio
import os
import sys
import httpx

# Ensure we can import from services
sys.path.append(os.getcwd())

from services.docling_client import DoclingClient

async def main():
    print(f"Httpx version: {httpx.__version__}")
    
    # Test cases: localhost vs 127.0.0.1
    urls = ["http://localhost:5001", "http://127.0.0.1:5001"]
    
    for url in urls:
        print(f"\n--- Testing URL: {url} ---")
        client = DoclingClient(base_url=url)
        
        # 1. Health
        try:
            health = await client.health_check()
            print(f"Health: {health}")
        except Exception as e:
            print(f"Health Check Failed: {e}")

        # 2. Conversion
        with open("test.txt", "w") as f:
            f.write("test content")
            
        try:
            res = await client.convert_file("test.txt")
            print("Conversion Success!")
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e}")
            print(f"Response URL: {e.response.url}")
            print(f"Response Code: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
            print(f"Request Headers: {e.request.headers}")
        except Exception as e:
            print(f"Other Error: {e}")
            
    if os.path.exists("test.txt"):
        os.remove("test.txt")

if __name__ == "__main__":
    asyncio.run(main())
