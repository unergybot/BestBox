
import sys
import os
import json
import asyncio
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.document_tools import analyze_document_realtime

def test_excel_analysis():
    excel_path = "docs/1947688(ED736A0501)-case.xlsx"
    if not os.path.exists(excel_path):
        print(f"File not found: {excel_path}")
        return

    print(f"Testing analysis on: {excel_path}")
    
    # Run the tool (synchronously as it's wrapped)
    result_json = analyze_document_realtime(excel_path)
    result = json.loads(result_json)
    
    if result.get("status") == "success":
        print("✅ Analysis successful")
        print(f"Summary: {result['analysis'].get('summary')[:100]}...")
        print(f"Original Type: {result.get('original_type')}")
        print(f"Extracted Images: {len(result['analysis'].get('extracted_images', []))}")
    else:
        print(f"❌ Analysis failed: {result.get('message')}")
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    test_excel_analysis()
