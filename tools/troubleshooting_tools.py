"""
Troubleshooting Knowledge Base Tools

Tools for searching and retrieving equipment troubleshooting cases.
Integrates with the troubleshooting KB built from 1000+ Excel files.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.tools import tool
from typing import Optional
import json
import logging
import re

from services.troubleshooting.searcher import TroubleshootingSearcher
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from tools.document_tools import analyze_document_realtime


logger = logging.getLogger(__name__)

# Initialize searcher (singleton)
_searcher = None


def get_searcher():
    """Get or create searcher instance"""
    global _searcher
    if _searcher is None:
        _searcher = TroubleshootingSearcher()
    return _searcher


def _normalize_troubleshooting_query(raw_query: str) -> str:
    q = (raw_query or "").strip()
    if not q:
        return q

    # Extract core subject from common wrappers/prefixes (keep the defect term).
    m = re.match(r"^(我|我们)?(遇到了|遇到|碰到|发现)(.*?)(问题|异常|不良|缺陷)[:：]?\s*(.*)$", q)
    if m:
        core = (m.group(3) or "").strip()
        tail = (m.group(5) or "").strip()
        q = core if core else tail

    q = re.sub(r"^(请|帮我|帮忙|麻烦)?(查找|搜索|看看|分析|解决|处理)\s*", "", q)

    # Remove common suffixes for Chinese question phrasing.
    q = re.sub(r"(怎么解决|如何解决|怎么处理|如何处理|怎么办|如何|怎么|解决方法|解决方案|有什么解决方案|有什么解决办法|原因是什么|是什么原因|是什么|有哪些|有啥)\??$", "", q)
    q = q.strip(" \t\n\r\u3000?？!！。．，,、:：;；")
    q = q.lstrip("，,、:：;；")
    q = q.rstrip("的")

    # If the query contains a known defect keyword, prefer the canonical term.
    keyword_map = {
        "披锋": "产品披锋",
        "拉白": "拉白",
        "火花纹": "火花纹残留",
        "脏污": "模具表面污染",
        "污染": "模具表面污染",
    }
    for needle, canonical in keyword_map.items():
        if needle in q:
            return canonical

    return q


@tool
def search_troubleshooting_kb(
    query: str,
    top_k: int = 5,
    part_number: Optional[str] = None,
    trial_version: Optional[str] = None,
    only_successful: bool = False
) -> str:
    """
    搜索故障排除知识库，查找设备问题的解决方案。

    Search the troubleshooting knowledge base for equipment issues and solutions.
    Contains 1000+ real troubleshooting cases with detailed solutions from production.

    Args:
        query: 搜索查询（问题描述或关键词）/ Search query (problem description or keywords)
            Examples: "产品披锋", "模具表面污染", "火花纹残留", "mold defects"
        top_k: 返回结果数量 / Number of results to return (default: 5)
        part_number: 零件号过滤 / Filter by part number (optional)
            Example: "1947688"
        trial_version: 试模版本过滤 (T0/T1/T2) / Filter by trial version (optional)
            Example: "T2"
        only_successful: 仅显示成功的解决方案 / Only show successful solutions (default: False)

    Returns:
        JSON string with search results including problems, solutions, trial results, and related images

    Examples:
        - search_troubleshooting_kb("产品披锋怎么解决")
        - search_troubleshooting_kb("mold surface contamination", part_number="1947688")
        - search_troubleshooting_kb("火花纹残留", only_successful=True)
        - search_troubleshooting_kb("T2阶段的问题", trial_version="T2")
    """
    try:
        logger.info(f"Searching troubleshooting KB: query='{query}', top_k={top_k}")

        normalized_query = _normalize_troubleshooting_query(query)
        if normalized_query and normalized_query != query:
            logger.info(f"Normalized troubleshooting query: '{query}' -> '{normalized_query}'")

        # Build filters
        filters = {}
        if part_number:
            filters['part_number'] = part_number
        if trial_version:
            filters['trial_version'] = trial_version
        if only_successful:
            filters['result'] = 'OK'

        # Search
        searcher = get_searcher()
        results = searcher.search(
            query=normalized_query or query,
            top_k=top_k,
            filters=filters if filters else None,
            classify=True  # Enable LLM-based query classification
        )

        # Format for agent consumption
        formatted_results = {
            "query": query,
            **({"normalized_query": normalized_query} if normalized_query and normalized_query != query else {}),
            "search_mode": results['mode'],
            "total_found": results['total_found'],
            "results": []
        }

        for item in results['results']:
            if item['type'] == 'issue':
                formatted_item = {
                    "result_type": "specific_solution",
                    "relevance_score": round(item['score'], 3),
                    "case_id": item['case_id'],
                    "part_number": item['part_number'],
                    "issue_number": item['issue_number'],
                    "problem": item['problem'],
                    "solution": item['solution'],
                    "trial_version": item['trial_version'],
                    "result_t1": item.get('result_t1'),
                    "result_t2": item.get('result_t2'),
                    "success_status": item.get('result_t2') or item.get('result_t1'),
                    "defect_types": item.get('defect_types', []),
                    "has_images": len(item.get('images', [])) > 0,
                    "image_count": len(item.get('images', [])),
                    "vlm_confidence": item.get('vlm_confidence'),
                    "severity": item.get('severity'),
                    "tags": item.get('tags', []),
                    "key_insights": item.get('key_insights', []),
                    "suggested_actions": item.get('suggested_actions', []),
                    "images": [
                        {
                            "image_id": img['image_id'],
                            "image_url": f"/api/troubleshooting/images/{img['image_id']}",
                            "description": img.get('vl_description', 'Image available'),
                            "defect_type": img.get('defect_type', '')
                        }
                        for img in item.get('images', [])  # Return all images
                    ]
                }

            elif item['type'] == 'case':
                formatted_item = {
                    "result_type": "full_case",
                    "relevance_score": round(item['score'], 3),
                    "case_id": item['case_id'],
                    "part_number": item['part_number'],
                    "material": item['material'],
                    "total_issues": item['total_issues'],
                    "summary": item.get('text_summary', ''),
                    "source_file": item.get('source_file')
                }

            else:
                formatted_item = item

            formatted_results['results'].append(formatted_item)

        return json.dumps(formatted_results, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Troubleshooting search failed: {e}")
        return json.dumps({
            "error": f"Search failed: {str(e)}",
            "query": query
        }, ensure_ascii=False)


@tool
def get_troubleshooting_case_details(case_id: str) -> str:
    """
    获取完整的故障排除案件详情，包括所有问题和图像。

    Get complete details for a specific troubleshooting case including all issues and images.
    Use this when you need full information about a case found in search results.

    Args:
        case_id: 案件ID（如 "TS-1947688-ED736A0501"）/ Case ID (e.g., "TS-1947688-ED736A0501")
            You can get this from search_troubleshooting_kb results

    Returns:
        JSON string with complete case details including metadata, all issues, solutions, and images

    Example:
        - get_troubleshooting_case_details("TS-1947688-ED736A0501")
    """
    try:
        logger.info(f"Fetching case details: {case_id}")

        # Connect to Qdrant
        qdrant = QdrantClient(host="localhost", port=6333)

        # Get case-level info
        case_results = qdrant.scroll(
            collection_name="troubleshooting_cases",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="case_id",
                        match=MatchValue(value=case_id)
                    )
                ]
            ),
            limit=1,
            with_payload=True
        )

        if not case_results[0]:
            return json.dumps({
                "error": f"Case {case_id} not found in knowledge base"
            }, ensure_ascii=False)

        case_data = case_results[0][0].payload

        # Get all issues for this case
        issue_results = qdrant.scroll(
            collection_name="troubleshooting_issues",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="case_id",
                        match=MatchValue(value=case_id)
                    )
                ]
            ),
            limit=100,
            with_payload=True
        )

        issues = []
        for issue_point in issue_results[0]:
            issue = issue_point.payload
            issues.append({
                "issue_number": issue['issue_number'],
                "trial_version": issue.get('trial_version'),
                "category": issue.get('category'),
                "problem": issue['problem'],
                "solution": issue['solution'],
                "result_t1": issue.get('result_t1'),
                "result_t2": issue.get('result_t2'),
                "success_status": issue.get('result_t2') or issue.get('result_t1'),
                "defect_types": issue.get('defect_types', []),
                "has_images": issue.get('has_images', False),
                "image_count": issue.get('image_count', 0),
                "images": [
                    {
                        "image_id": img['image_id'],
                        "image_url": f"/api/troubleshooting/images/{img['image_id']}",
                        "description": img.get('vl_description', 'Image available'),
                        "defect_type": img.get('defect_type', '')
                    }
                    for img in issue.get('images', [])
                ]
            })

        # Sort by issue number
        issues.sort(key=lambda x: x['issue_number'])

        result = {
            "case_id": case_id,
            "part_number": case_data['part_number'],
            "internal_number": case_data.get('internal_number'),
            "mold_type": case_data.get('mold_type'),
            "material": case_data.get('material'),
            "total_issues": case_data['total_issues'],
            "source_file": case_data.get('source_file'),
            "issues": issues,
            "summary": f"案件 {case_id} 包含 {len(issues)} 个故障排除问题。零件号: {case_data['part_number']}，材料: {case_data.get('material', 'N/A')}"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Failed to get case details: {e}")
        return json.dumps({
            "error": f"Failed to retrieve case: {str(e)}",
            "case_id": case_id
        }, ensure_ascii=False)



@tool
def find_similar_defects(file_path: str) -> str:
    """
    通过上传的图像查找相似的缺陷案例。
    Find similar defect cases based on an uploaded image.

    This tool:
    1. Analyzes the visual content of the image (VLM).
    2. Identifies defects, features, and anomalies.
    3. Searches the knowledge base for cases with similar descriptions.

    Args:
        file_path: 图像文件路径 / Path to the image file (or document)

    Returns:
        JSON string with visual analysis and found similar cases.
    """
    try:
        logger.info(f"Finding similar defects for: {file_path}")

        # Step 1: Analyze Document/Image (VLM)
        # We call the existing tool logic directly or via invoke if needed.
        # Since we are inside python, we can just call the function wrapper if it wasn't a tool,
        # but since it is a tool, let's look at how to call it.
        # Ideally we refactor the logic out, but calling the tool function is fine if arguments match.
        # Alternatively, use logic shared between them?
        # Let's call analyze_document_realtime.
        
        # Note: analyze_document_realtime returns a JSON string.
        vlm_json = analyze_document_realtime(file_path) # Call locally
        vlm_result = json.loads(vlm_json)

        if vlm_result.get("status") != "success":
            return json.dumps({
                "error": "Failed to analyze image for similarity search",
                "details": vlm_result.get("message")
            }, ensure_ascii=False)

        analysis = vlm_result.get("analysis", {})
        
        # Step 2: Construct Search Query
        # We combine defect type, summary, and tags to form a rich semantic query.
        query_parts = []
        
        # Add defect types from extracted images
        for img in analysis.get("extracted_images", []):
            if img.get("defect_type"):
                query_parts.append(img["defect_type"])
            if img.get("description"):
                query_parts.append(img["description"])

        # Add key insights
        if analysis.get("key_insights"):
            query_parts.extend(analysis["key_insights"][:2]) # Top 2 insights

        # Add tags
        if analysis.get("tags"):
            query_parts.extend(analysis["tags"][:3]) # Top 3 tags

        # Add summary if short enough, otherwise rely on parts
        if analysis.get("summary"):
             query_parts.append(analysis["summary"][:200]) # Limit length

        search_query = " ".join(query_parts)
        logger.info(f"Generated search query: {search_query[:100]}...")

        # Step 3: Search Knowledge Base
        searcher = get_searcher()
        # We focus on ISSUE level to find specific defects
        search_results = searcher.search(
            query=search_query,
            top_k=5,
            classify=False # Force vector search
        )

        # Step 4: Format Response
        response = {
            "query_generated": search_query,
            "visual_analysis": {
                "summary": analysis.get("summary"),
                "defect_types": [img.get("defect_type") for img in analysis.get("extracted_images", []) if img.get("defect_type")],
                "confidence": analysis.get("confidence")
            },
            "similar_cases": []
        }

        for item in search_results["results"]:
            if item["type"] == "issue":
                response["similar_cases"].append({
                    "case_id": item["case_id"],
                    "issue_number": item["issue_number"],
                    "problem": item["problem"],
                    "solution": item["solution"],
                    "relevance_score": item["score"],
                    "similarity_reason": "Visual & Semantic Match", # Placeholder
                    "images": [
                        {
                            "image_url": f"/api/troubleshooting/images/{img['image_id']}",
                            "description": img.get('vl_description', '')
                        }
                        for img in item.get('images', [])[:1]
                    ]
                })

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Find similar defects failed: {e}")
        return json.dumps({
            "error": str(e)
        }, ensure_ascii=False)


# Export tools list for easy import
troubleshooting_tools = [
    search_troubleshooting_kb,
    get_troubleshooting_case_details,
    find_similar_defects
]


if __name__ == "__main__":
    # Test tools
    print("Testing Troubleshooting Tools")
    print("=" * 70)
    print()

    # Test 1: Search
    print("Test 1: Searching for '产品披锋'")
    print("-" * 70)
    result = search_troubleshooting_kb.invoke({
        "query": "产品披锋",
        "top_k": 3
    })

    data = json.loads(result)
    print(f"Found: {data['total_found']} results")
    print(f"Mode: {data['search_mode']}")

    if data['results']:
        print(f"\nTop result:")
        top = data['results'][0]
        print(f"  Problem: {top['problem'][:60]}...")
        print(f"  Solution: {top['solution'][:60]}...")
        print(f"  Score: {top['relevance_score']}")
        print(f"  Success: {top['success_status']}")
        print(f"  Images: {top['image_count']}")

    print()
    print()

    # Test 2: Get case details
    print("Test 2: Getting case details")
    print("-" * 70)
    result = get_troubleshooting_case_details.invoke({
        "case_id": "TS-1947688-ED736A0501"
    })

    data = json.loads(result)
    if 'error' not in data:
        print(f"Case: {data['case_id']}")
        print(f"Part Number: {data['part_number']}")
        print(f"Total Issues: {data['total_issues']}")
        print(f"\nFirst issue:")
        if data['issues']:
            issue = data['issues'][0]
            print(f"  #{issue['issue_number']}: {issue['problem'][:50]}...")
            print(f"  Status: {issue['success_status']}")
    else:
        print(f"Error: {data['error']}")

    print()
    print("✅ Tool tests complete")
