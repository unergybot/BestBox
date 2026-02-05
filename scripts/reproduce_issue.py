
import sys
import os
import json
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from services.troubleshooting.searcher import TroubleshootingSearcher
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

def analyze_search_results():
    searcher = TroubleshootingSearcher()

from tools.troubleshooting_tools import _normalize_troubleshooting_query

def analyze_search_results():
    searcher = TroubleshootingSearcher()
    client = searcher.qdrant
    
    raw_query = "尺寸NG cases"
    normalized_query = _normalize_troubleshooting_query(raw_query)
    
    print(f"Normalization Check:")
    print(f"  Raw: '{raw_query}'")
    print(f"  Normalized: '{normalized_query}'")
    
    # We want to verify that the tool (which uses normalized_query) will get better results
    queries = [normalized_query]
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"Testing Normalized Query: '{query}'")
        
        # 1. Normal search
        # Note: classifier defaults to ISSUE_LEVEL if disabled, which is what we want
        results = searcher.search(query, top_k=20, classify=False)
        
        print(f"\nFound {len(results['results'])} results:")
        found_issue_numbers = []
        
        for i, res in enumerate(results['results']):
            if res['type'] == 'issue':
                found_issue_numbers.append(res['issue_number'])
                print(f"  {i+1}. Issue #{res['issue_number']} (Score: {res['score']:.4f})")
                print(f"     Problem: {res['problem']}")
                print(f"     Tags: {res['tags']}")
                print(f"     VLM Processed: {res['vlm_processed']}")
                print(f"     VLM Confidence: {res['vlm_confidence']}")
                print(f"     Severity: {res['severity']}")
                print(f"     Images ({len(res.get('images', []))}):")
                for img in res.get('images', []):
                    print(f"       - {img.get('image_id')} ({img.get('description', '')[:30]}...)")

                
        # Check for expected issues
        expected = [12, 16, 17, 18]
        print(f"\nExpected: {expected}")
        print(f"Found (Top 20): {found_issue_numbers}")
        
        missing = [x for x in expected if x not in found_issue_numbers]
        if missing:
            print(f"❌ Missing issues in Top 20: {missing}")
        else:
            print(f"✅ All expected issues found in Top 20.")
            
        # Check if 5, 6, 4 are higher than expected
        bad_results = [5, 6, 4]
        bad_ranks = {}
        for i, res in enumerate(results['results']):
            if res['type'] == 'issue' and res['issue_number'] in bad_results:
                bad_ranks[res['issue_number']] = i + 1
        
        print(f"Ranks of #5, #6, #4: {bad_ranks}")


if __name__ == "__main__":
    analyze_search_results()
