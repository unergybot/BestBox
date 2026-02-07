import asyncio
import os
import sys

# Ensure we can import from services
sys.path.append(os.getcwd())

from services.docling_client import DoclingClient

async def main():
    print("Testing Docling Client Connection...")
    # Force localhost if not set, to reproduce default
    url = os.getenv("DOCLING_SERVE_URL", "http://localhost:5001")
    print(f"Target URL: {url}")
    
    client = DoclingClient(base_url=url)
    
    try:
        print("1. Testing Health Check...")
        health = await client.health_check()
        print(f"Health: {health}")
    except Exception as e:
        print(f"Health Check Failed: {e}")

    try:
        print("\n2. Testing File Conversion (Expect 422 or Success, not 404)...")
        # create dummy file
        with open("test.txt", "w") as f:
            f.write("test content")
            
        try:
            res = await client.convert_file("test.txt")
            print(f"Conversion Result: {res.keys()}")
        except Exception as e:
            print(f"Conversion Failed: {e}")
            
    finally:
        if os.path.exists("test.txt"):
            os.remove("test.txt")

if __name__ == "__main__":
    asyncio.run(main())
