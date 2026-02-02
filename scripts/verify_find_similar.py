
import sys
import os
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.troubleshooting_tools import find_similar_defects

def test_find_similar():
    image_path = "docs/1947688(ED736A0501)-case.xlsx"

    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    print(f"Testing find_similar_defects on: {image_path}")
    
    # Run the tool
    # Using 'invoke' if it was a LangChain tool, but here treating as function
    try:
        result_json = find_similar_defects(image_path)
        result = json.loads(result_json)
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        return
    
    if "error" in result:
        print(f"❌ Failed result: {result['error']}")
        return

    print("\n✅ Visual Analysis:")
    analysis = result.get("visual_analysis", {})
    print(f"   Summary: {analysis.get('summary')[:100]}...")
    
    print(f"\n✅ Generated Query: \"{result.get('query_generated')}\"")
    
    cases = result.get("similar_cases", [])
    print(f"\n✅ Found {len(cases)} similar cases:")
    for case in cases:
        print(f"   - Case {case['case_id']} #{case['issue_number']}")
        print(f"     Score: {case['relevance_score']:.3f}")
        print(f"     Problem: {case['problem'][:50]}...")

if __name__ == "__main__":
    test_find_similar()
