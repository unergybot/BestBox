
import sys
import os
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.troubleshooting_tools import find_similar_defects

def test_find_similar():
    # Use one of the images extracted in Phase 1/2
    # We copied one to docs/test_images in previous step if available, 
    # otherwise we rely on what's leftover or re-use extraction.
    # Since we deleted extracted folder in Phase 2 cleanup, we might need a file.
    # Let's check for it.
    
    image_path = "docs/test_images/flash_example.jpg"
    
    # Fallback: if not found, use the Excel again, knowing find_similar *might* handle it 
    # BUT find_similar expects an image primarily. 
    # Actually, analyze_document_realtime handles PDF/Excel too. 
    # Let's try the Excel file directly as "find similar to this case file".
    if not os.path.exists(image_path):
        print(f"Image not found at {image_path}, trying Excel...")
        image_path = "docs/1947688(ED736A0501)-case.xlsx"

    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    print(f"Testing find_similar_defects on: {image_path}")
    
    # Run the tool
    result_json = find_similar_defects(image_path)
    result = json.loads(result_json)
    
    if "error" in result:
        print(f"❌ Failed: {result['error']}")
        return

    print("\n✅ Visual Analysis:")
    analysis = result.get("visual_analysis", {})
    print(f"   Summary: {analysis.get('summary')[:100]}...")
    print(f"   Defects: {analysis.get('defect_types')}")
    
    print(f"\n✅ Generated Query: \"{result.get('query_generated')}\"")
    
    print(f"\n✅ Found {len(result.get('similar_cases', []))} similar cases:")
    for case in result.get("similar_cases", []):
        print(f"   - Case {case['case_id']} #{case['issue_number']}")
        print(f"     Score: {case['relevance_score']:.3f}")
        print(f"     Problem: {case['problem'][:50]}...")

if __name__ == "__main__":
    test_find_similar()
