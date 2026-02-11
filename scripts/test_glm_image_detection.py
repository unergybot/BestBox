#!/usr/bin/env python3
"""Test GLM-SDK image detection accuracy with new config."""

import sys
import json
import httpx
import subprocess
from pathlib import Path

# Copy PDF to GLM-SDK container
pdf_path = Path("docs/ppd407.pdf")
container_path = "/app/shared/test_ppd407.pdf"

print(f"📄 Testing GLM-SDK image detection with: {pdf_path}")
print("="*60)

# Copy to container
print("\n1. Copying PDF to GLM-SDK container...")
result = subprocess.run(
    ["docker", "cp", str(pdf_path), f"bestbox-glm-sdk:{container_path}"],
    capture_output=True,
    text=True
)
if result.returncode != 0:
    print(f"❌ Failed to copy: {result.stderr}")
    sys.exit(1)
print("✅ PDF copied successfully")

# Call GLM-SDK API
print("\n2. Calling GLM-SDK API...")
try:
    response = httpx.post(
        "http://localhost:5002/glmocr/parse",
        json={"images": [container_path]},
        timeout=120.0
    )
    response.raise_for_status()
except Exception as e:
    print(f"❌ API call failed: {e}")
    subprocess.run(["docker", "exec", "bestbox-glm-sdk", "rm", "-f", container_path], check=False)
    sys.exit(1)

print("✅ API call successful")

# Parse results
result = response.json()
json_result = result.get("json_result", [])

# Cleanup
subprocess.run(["docker", "exec", "bestbox-glm-sdk", "rm", "-f", container_path], check=False)

# Analyze image detections on page 3
print("\n3. Analyzing image detections on Page 3...")
print("="*60)

if len(json_result) < 3:
    print(f"⚠️ Only {len(json_result)} pages detected")
    sys.exit(1)

page3_elements = json_result[2]  # Page 3 (index 2)
images = []

for elem in page3_elements:
    if elem.get("type") == "image" or "bbox_2d" in elem:
        bbox = elem.get("bbox_2d")
        if bbox:
            images.append({
                "bbox": bbox,
                "width": bbox[2] - bbox[0],
                "height": bbox[3] - bbox[1]
            })

print(f"\n📊 Found {len(images)} images on page 3\n")

for i, img in enumerate(images):
    print(f"Image {i}:")
    print(f"  Bbox: {img['bbox']}")
    print(f"  Size: {img['width']:.1f} × {img['height']:.1f} points")
    print()

# Expected: Should detect 2 separate images (Black specks + Brittleness)
# Previously: Was detecting 1 merged image
if len(images) >= 2:
    print("✅ SUCCESS: Multiple images detected separately!")
    print("   The bbox merge fix is working correctly.")
else:
    print("⚠️ WARNING: Still detecting images as merged.")
    print("   Expected at least 2 separate images on page 3.")

print("\n" + "="*60)
print(f"Total images detected: {len(images)}")
