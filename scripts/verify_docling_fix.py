import asyncio
import os
import sys

# Ensure we can import from services
sys.path.append(os.getcwd())

from services.docling_client import DoclingClient

async def main():
    print("Verifying Docling Fix...")
    if not os.path.exists("test.png"):
        print("Error: test.png not found. Run make_dummy_image.py first.")
        # create it if needed
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (100, 30), color = (73, 109, 137))
        d = ImageDraw.Draw(img)
        d.text((10,10), "Hello World", fill=(255, 255, 0))
        img.save('test.png')

    client = DoclingClient()
    
    try:
        print("Calling convert_file (should use async path now)...")
        # Increase timeout for async processing
        client.timeout = 60.0
        res = await client.convert_file("test.png")
        print("\nConversion Success!")
        print(f"Keys: {res.keys()}")
        if 'md' in res:
            print(f"Markdown length: {len(res['md'])}")
    except Exception as e:
        print(f"\nVerification Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
