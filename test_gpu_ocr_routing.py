#!/usr/bin/env python3
"""
Test script to verify GPU OCR routing is working.
"""
import sys
from pathlib import Path

# Check if code changes are in place
admin_endpoints = Path("services/admin_endpoints.py")
content = admin_endpoints.read_text()

print("=" * 70)
print("GPU OCR ROUTING VERIFICATION")
print("=" * 70)

# Check for the routing code
if 'if ext == ".pdf":' in content:
    print("✅ PDF routing code found")

    if 'MoldDocumentIngester' in content:
        print("✅ MoldDocumentIngester import found")
    else:
        print("❌ MoldDocumentIngester import NOT found")
        sys.exit(1)

    if 'GPU OCR service' in content:
        print("✅ GPU OCR comment found")
    else:
        print("⚠️  GPU OCR comment not found (non-critical)")

    if 'processing_method = "gpu_ocr"' in content:
        print("✅ GPU OCR processing method tag found")
    else:
        print("❌ GPU OCR processing method tag NOT found")
        sys.exit(1)

    print("\n✅ All code changes are in place!")
    print("\nNext steps:")
    print("1. Restart the agent API to load changes:")
    print("   pkill -f 'python services/agent_api.py'")
    print("   python services/agent_api.py &")
    print("\n2. Test upload:")
    print('   curl -X POST "http://localhost:8000/admin/documents/upload?collection=test_gpu" \\')
    print('     -H "admin-token: bestbox-admin-token" \\')
    print('     -F "file=@~/MyCode/StarRapid.pdf"')

else:
    print("❌ PDF routing code NOT found")
    print("\nThe code changes may not have been applied correctly.")
    sys.exit(1)
