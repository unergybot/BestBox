#!/usr/bin/env python3
"""Analyze the extracted troubleshooting case to verify image-to-row mapping."""

import json
from pathlib import Path
from collections import defaultdict

def analyze_case(json_path: str):
    """Analyze case JSON and report image distribution."""
    with open(json_path, 'r', encoding='utf-8') as f:
        case = json.load(f)
    
    print(f"Case ID: {case['case_id']}")
    print(f"Total Issues: {case['total_issues']}")
    print(f"Source File: {case['source_file']}")
    print("\n" + "="*80)
    print("IMAGE DISTRIBUTION BY ISSUE")
    print("="*80)
    
    total_images = 0
    match_types = defaultdict(int)
    mapped_image_ids = set()
    
    for issue in case['issues']:
        issue_num = issue['issue_number']
        excel_row = issue['excel_row']
        problem = issue['problem'][:50] if issue['problem'] else "N/A"
        
        images = issue.get('images', [])
        image_count = len(images)
        total_images += image_count
        
        print(f"\nIssue #{issue_num:2d} | Row {excel_row:4d} | Images: {image_count}")
        print(f"  Problem: {problem}...")
        
        if images:
            for i, img in enumerate(images, 1):
                anchor = img.get('anchor', {})
                spatial = img.get('spatial_match', {})
                
                row_start = anchor.get('row_start', 0)
                row_end = anchor.get('row_end', 0)
                match_type = spatial.get('type', 'unknown')
                confidence = spatial.get('confidence', 0)
                row_dist = spatial.get('row_distance', 0)
                image_id = img.get('image_id', 'unknown')
                
                mapped_image_ids.add(image_id)
                match_types[match_type] += 1
                
                print(f"    Image {i}: {image_id} | Row {row_start}-{row_end} | "
                      f"Match: {match_type} | Conf: {confidence:.2f} | "
                      f"Dist: {row_dist}")
        else:
            print("    [No images mapped]")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total images mapped: {total_images}")
    print(f"Total images extracted (expected): {case.get('vlm_validation', {}).get('total_images', 'N/A')}")
    print("\nMatch type distribution:")
    for match_type, count in sorted(match_types.items()):
        print(f"  {match_type}: {count}")
    
    issues_no_images = [i for i in case['issues'] if not i.get('images')]
    if issues_no_images:
        print(f"\n⚠️  Issues with NO images: {len(issues_no_images)}")
        for issue in issues_no_images:
            print(f"   Issue #{issue['issue_number']} at Row {issue['excel_row']}")
    
    return case, mapped_image_ids

if __name__ == "__main__":
    json_path = "data/troubleshooting/processed/TS-1947688-ED736A0501.json"
    analyze_case(json_path)
