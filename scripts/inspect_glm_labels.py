#!/usr/bin/env python3
"""Inspect what labels GLM-SDK actually returns."""

import sys
import json
import httpx
import subprocess
from pathlib import Path

pdf_path = Path("docs/ppd407.pdf")
container_path = "/app/shared/test_ppd407_inspect.pdf"

print("🔍 Inspecting GLM-SDK element labels...")
print("="*60)

# Copy to container
subprocess.run(
    ["docker", "cp", str(pdf_path), f"bestbox-glm-sdk:{container_path}"],
    capture_output=True,
    check=True
)

# Call API
try:
    response = httpx.post(
        "http://localhost:5002/glmocr/parse",
        json={"images": [container_path]},
        timeout=120.0
    )
    response.raise_for_status()
except Exception as e:
    print(f"❌ API call failed: {e}")
    sys.exit(1)

result = response.json()
json_result = result.get("json_result", [])

# Cleanup
subprocess.run(["docker", "exec", "bestbox-glm-sdk", "rm", "-f", container_path], check=False)

# Analyze Page 3
if len(json_result) < 3:
    print(f"⚠️ Only {len(json_result)} pages")
    sys.exit(1)

page3_elements = json_result[2]

print(f"\nPage 3: {len(page3_elements)} total elements\n")

# Group by label/type
label_counts = {}
for elem in page3_elements:
    label = elem.get("label", "NONE")
    elem_type = elem.get("type", "NONE")
    key = f"{label} (type={elem_type})"
    label_counts[key] = label_counts.get(key, 0) + 1

    # Show first few with bbox
    if label_counts[key] <= 3 and (elem.get("bbox_2d") or elem.get("bbox")):
        bbox = elem.get("bbox_2d") or elem.get("bbox")
        print(f"Element: label='{label}', type='{elem_type}', bbox={bbox}")

print(f"\n📊 Label distribution on Page 3:")
for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
    print(f"  {label}: {count}")
