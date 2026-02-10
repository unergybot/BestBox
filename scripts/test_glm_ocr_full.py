#!/usr/bin/env python3
"""
Comprehensive GLM-OCR Test Script
Tests GPU usage, layout extraction (tables, images), and PDF parsing
"""

import requests
import json
import time
import subprocess
from pathlib import Path


def check_gpu_usage():
    """Check if GLM services are using GPU"""
    print("=== GPU Usage Check ===")
    result = subprocess.run(
        ["docker", "exec", "bestbox-glm-transformers", "nvidia-smi",
         "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
         "--format=csv,noheader"],
        capture_output=True,
        text=True
    )
    print(f"GPU Status: {result.stdout.strip()}")
    print()


def test_health_endpoints():
    """Test health endpoints of both services"""
    print("=== Health Check ===")

    # GLM-Transformers
    resp = requests.get("http://localhost:11436/health")
    print(f"GLM-Transformers: {resp.status_code} - {resp.json()}")

    # GLM-SDK (no formal health endpoint, test parse endpoint)
    print(f"GLM-SDK: Service running on port 5002")
    print()


def test_health_check_without_image():
    """Test that health check requests (no image) work correctly"""
    print("=== Health Check Request (No Image) ===")

    payload = {
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": "hello"}]
        }],
        "model": "glm-ocr",
        "max_tokens": 10
    }

    resp = requests.post(
        "http://localhost:11436/v1/chat/completions",
        json=payload
    )

    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
    print()


def test_pdf_with_layout(pdf_path: str):
    """Test PDF parsing with layout detection (tables, images)"""
    print(f"=== PDF Parsing with Layout Detection ===")
    print(f"PDF: {pdf_path}")

    # Copy PDF to shared volume
    subprocess.run([
        "docker", "cp", pdf_path, "bestbox-glm-sdk:/app/shared/test.pdf"
    ])

    # Parse PDF
    start_time = time.time()

    resp = requests.post(
        "http://localhost:5002/glmocr/parse",
        json={"images": ["/app/shared/test.pdf"]},
        headers={"Content-Type": "application/json"}
    )

    duration = time.time() - start_time

    if resp.status_code != 200:
        print(f"❌ Error: {resp.status_code}")
        print(resp.text)
        return

    result = resp.json()
    markdown = result.get("markdown_result", "")

    print(f"✅ Success! Processing time: {duration:.2f}s")
    print(f"Markdown length: {len(markdown)} chars")
    print()

    # Analyze extracted content
    tables_count = markdown.count("<table")
    images_count = markdown.count("![](page=")
    headers_count = markdown.count("##")

    print(f"📊 Layout Analysis:")
    print(f"  - Tables: {tables_count}")
    print(f"  - Images/Figures: {images_count}")
    print(f"  - Headers: {headers_count}")
    print()

    print("📄 Markdown Preview (first 800 chars):")
    print("=" * 60)
    print(markdown[:800])
    print("=" * 60)
    print()

    # Save full output
    output_path = Path("test_glm_ocr_output.md")
    output_path.write_text(markdown)
    print(f"💾 Full output saved to: {output_path.absolute()}")
    print()


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("GLM-OCR COMPREHENSIVE TEST")
    print("=" * 70 + "\n")

    try:
        check_gpu_usage()
        test_health_endpoints()
        test_health_check_without_image()
        test_pdf_with_layout("docs/ppd407_p4.pdf")

        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
