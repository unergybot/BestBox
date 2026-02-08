import requests
import base64
import json
import time
from PIL import Image, ImageDraw
import io

def create_dummy_image():
    # Create an image with text "Hello World"
    img = Image.new('RGB', (400, 100), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10,10), "Hello World", fill=(0, 0, 0))
    # Add a rectangle to simulate a layout element
    d.rectangle([(20, 40), (100, 80)], outline="black")
    
    # Convert to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def test_sdk():
    url = "http://localhost:5002/glmocr/parse"
    print(f"Testing {url}...")
    
    # Create image
    img_data = create_dummy_image()
    
    # Payload
    payload = {
        "images": [img_data]
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=300)
        end_time = time.time()
        
        print(f"Status Code: {response.status_code}")
        print(f"Time Taken: {end_time - start_time:.2f}s")
        
        if response.status_code == 200:
            result = response.json()
            print("Response JSON keys:", result.keys())
            if "markdown" in result:
                print("Markdown Output:")
                print(result["markdown"])
            if "json_result" in result:
                print("JSON Result Summary:")
                for item in result["json_result"]:
                    if isinstance(item, list):
                        for subitem in item:
                             print(f"  - {subitem.get('label', 'unknown')}: {subitem.get('content', '')[:50]}...")
                    else:
                        print(f"  - {item}")
        else:
            print("Error Response:", response.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_sdk()
