#!/usr/bin/env python3
"""Test label filtering logic directly."""

import sys
sys.path.insert(0, "/home/apexai/BestBox")

from services.admin_endpoints import _is_glm_image_element

# Mock Page 3 elements from GLM-SDK
test_elements = [
    {"label": "text", "bbox_2d": [43, 56, 215, 98]},            # Header - should REJECT
    {"label": "image", "bbox_2d": [45, 108, 272, 422]},         # Product photo - should ACCEPT
    {"label": "table", "bbox_2d": [290, 111, 955, 422]},        # Table - should REJECT
    {"label": "text", "bbox_2d": [44, 457, 193, 493]},          # Header - should REJECT
    {"label": "image", "bbox_2d": [45, 509, 273, 867]},         # Product photo - should ACCEPT
    {"label": "table", "bbox_2d": [289, 511, 954, 868]},        # Table - should REJECT
]

print("🧪 Testing label filtering logic...")
print("="*60)

accepted = []
rejected = []

for i, elem in enumerate(test_elements):
    result = _is_glm_image_element(elem)
    label = elem["label"]
    bbox = elem["bbox_2d"]

    status = "✅ ACCEPT" if result else "❌ REJECT"
    expected = "✅" if label == "image" else "❌"
    match = "✓" if (result and label == "image") or (not result and label != "image") else "✗ MISMATCH"

    print(f"{match} Element {i}: label='{label}' → {status} (expected: {expected})")

    if result:
        accepted.append((label, bbox))
    else:
        rejected.append((label, bbox))

print("\n" + "="*60)
print(f"📊 Results:")
print(f"  Accepted: {len(accepted)} (should be 2 images)")
print(f"  Rejected: {len(rejected)} (should be 4: 2 text + 2 tables)")

if len(accepted) == 2 and all(label == "image" for label, _ in accepted):
    print("\n✅ SUCCESS: Filtering working correctly!")
    print("   Only accepting actual images, rejecting text and tables.")
else:
    print("\n❌ FAILURE: Filtering not working as expected!")
    print(f"   Accepted labels: {[label for label, _ in accepted]}")
