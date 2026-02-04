"""
Troubleshooting Knowledge Base Tools

Tools for searching and retrieving equipment troubleshooting cases.
Integrates with the troubleshooting KB built from 1000+ Excel files.

Includes:
- Semantic search (vector-based)
- Structured search (SQL-based)
- Hybrid search (combined)
- Learning capabilities
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.tools import tool
from typing import Optional, Literal
import json
import logging
import re

from services.troubleshooting.searcher import TroubleshootingSearcher
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from tools.document_tools import analyze_document_realtime


logger = logging.getLogger(__name__)

# Initialize searchers (singletons)
_searcher = None
_hybrid_searcher = None


def get_searcher():
    """Get or create semantic searcher instance"""
    global _searcher
    if _searcher is None:
        _searcher = TroubleshootingSearcher()
    return _searcher


def get_hybrid_searcher():
    """Get or create hybrid searcher instance"""
    global _hybrid_searcher
    if _hybrid_searcher is None:
        try:
            from services.troubleshooting.hybrid_searcher import HybridSearcher
            _hybrid_searcher = HybridSearcher()
        except Exception as e:
            logger.warning(f"Failed to initialize hybrid searcher: {e}")
            return None
    return _hybrid_searcher


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

    # Remove common suffixes for Chinese question phrasing and English wrappers.
    q = re.sub(r"(怎么解决|如何解决|怎么处理|如何处理|怎么办|如何|怎么|解决方法|解决方案|有什么解决方案|有什么解决办法|原因是什么|是什么原因|是什么|有哪些|有啥|cases|case|案例|案件)\??$", "", q, flags=re.IGNORECASE)
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
        "尺寸": "产品尺寸",
        "尺寸NG": "产品尺寸NG",
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
    only_successful: bool = False,
    adaptive: bool = True
) -> str:
    """
    搜索故障排除知识库，查找设备问题的解决方案。

    Search the troubleshooting knowledge base for equipment issues and solutions.
    Contains 1000+ real troubleshooting cases with detailed solutions from production.

    Args:
        query: 搜索查询（问题描述或关键词）/ Search query (problem description or keywords)
            Examples: "产品披锋", "模具表面污染", "火花纹残留", "mold defects"
        top_k: 最大返回结果数量 / Maximum number of results to return (default: 5)
            When adaptive=True, actual count may vary based on relevance scores
        part_number: 零件号过滤 / Filter by part number (optional)
            Example: "1947688"
        trial_version: 试模版本过滤 (T0/T1/T2) / Filter by trial version (optional)
            Example: "T2"
        only_successful: 仅显示成功的解决方案 / Only show successful solutions (default: False)
        adaptive: 自适应结果数量 / Use adaptive result count based on relevance (default: True)
            When True, returns all highly relevant results (score >= 0.65) up to top_k*2,
            using score gap detection to find natural result boundaries.
            When False, returns exactly top_k results.

    Returns:
        JSON string with search results including problems, solutions, trial results, and related images

    Examples:
        - search_troubleshooting_kb("产品披锋怎么解决")
        - search_troubleshooting_kb("mold surface contamination", part_number="1947688")
        - search_troubleshooting_kb("火花纹残留", only_successful=True)
        - search_troubleshooting_kb("T2阶段的问题", trial_version="T2")
        - search_troubleshooting_kb("披锋", adaptive=False, top_k=3)  # Fixed count
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
            classify=True,  # Enable LLM-based query classification
            adaptive=adaptive  # Enable adaptive result count
        )

        # Format for agent consumption
        formatted_results = {
            "query": query,
            **({"normalized_query": normalized_query} if normalized_query and normalized_query != query else {}),
            "search_mode": results['mode'],
            "adaptive_mode": results.get('adaptive', False),
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


# ============================================================================
# NEW: Structured and Hybrid Search Tools
# ============================================================================


@tool
def search_troubleshooting_structured(
    query: str,
    top_k: int = 10,
    part_number: Optional[str] = None,
    material: Optional[str] = None,
    trial_version: Optional[str] = None,
    search_mode: Literal["AUTO", "STRUCTURED", "SEMANTIC", "HYBRID"] = "AUTO",
) -> str:
    """
    使用混合搜索查询故障排除数据库，支持SQL和语义搜索。

    Hybrid search combining SQL (structured) and vector (semantic) search.
    Automatically detects query intent and routes appropriately.

    Args:
        query: 搜索查询 / Search query
            Counting queries: "有多少个披锋问题", "T1成功的案例数"
            Semantic queries: "披锋怎么解决", "拉白的原因"
            Hybrid queries: "HIPS材料的披锋解决方案"
        top_k: 最大返回结果数量 / Maximum results (default: 10)
        part_number: 零件号过滤 / Filter by part number
        material: 材料过滤 / Filter by material (e.g., "HIPS", "ABS")
        trial_version: 试模版本过滤 / Filter by trial version (T0/T1/T2)
        search_mode: 搜索模式 / Search mode
            AUTO: Automatically detect intent (recommended)
            STRUCTURED: Force SQL-based search
            SEMANTIC: Force vector search
            HYBRID: Use both and fuse results

    Returns:
        JSON string with search results, including generated SQL for structured queries

    Examples:
        - search_troubleshooting_structured("有多少个披锋问题")  # Auto-detects STRUCTURED
        - search_troubleshooting_structured("披锋怎么解决")  # Auto-detects SEMANTIC
        - search_troubleshooting_structured("HIPS材料的披锋", material="HIPS")  # HYBRID
        - search_troubleshooting_structured("T1成功率", search_mode="STRUCTURED")
    """
    try:
        logger.info(f"Structured search: query='{query}', mode={search_mode}")

        hybrid_searcher = get_hybrid_searcher()
        if hybrid_searcher is None:
            # Fallback to semantic search
            logger.warning("Hybrid searcher not available, falling back to semantic")
            return search_troubleshooting_kb.invoke({
                "query": query,
                "top_k": top_k,
                "part_number": part_number,
                "trial_version": trial_version,
            })

        # Build filters
        filters = {}
        if part_number:
            filters["part_number"] = part_number
        if material:
            filters["material"] = material
        if trial_version:
            filters["trial_version"] = trial_version

        # Execute hybrid search
        results = hybrid_searcher.search(
            query=query,
            mode=search_mode,
            top_k=top_k,
            filters=filters if filters else None,
            return_sql=True,
        )

        # Format response
        response = {
            "query": results.get("query"),
            "expanded_query": results.get("expanded_query"),
            "search_mode": results.get("mode"),
            "intent_confidence": results.get("intent_confidence"),
            "synonyms_used": results.get("synonyms_used", []),
            "total_found": results.get("total_found", 0),
            "results": [],
        }

        if results.get("generated_sql"):
            response["generated_sql"] = results["generated_sql"]

        if results.get("error"):
            response["error"] = results["error"]

        # Format results
        for item in results.get("results", []):
            if item.get("type") == "issue":
                response["results"].append({
                    "result_type": "specific_solution",
                    "source": item.get("source", "unknown"),
                    "relevance_score": round(item.get("score", item.get("fusion_score", 0)), 3),
                    "case_id": item.get("case_id"),
                    "part_number": item.get("part_number"),
                    "issue_number": item.get("issue_number"),
                    "problem": item.get("problem"),
                    "solution": item.get("solution"),
                    "trial_version": item.get("trial_version"),
                    "result_t1": item.get("result_t1"),
                    "result_t2": item.get("result_t2"),
                    "defect_types": item.get("defect_types", []),
                })
            elif item.get("type") == "aggregation":
                response["results"].append({
                    "result_type": "aggregation",
                    "source": "structured",
                    **{k: v for k, v in item.items() if k not in ["type", "source"]},
                })
            else:
                response["results"].append(item)

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Structured search failed: {e}")
        return json.dumps({
            "error": f"Search failed: {str(e)}",
            "query": query,
        }, ensure_ascii=False)


@tool
def save_troubleshooting_learning(
    title: str,
    learning: str,
    learning_type: Literal["error_pattern", "type_gotcha", "user_correction", "date_format"] = "error_pattern",
    tables_affected: Optional[str] = None,
) -> str:
    """
    保存故障排除学习内容，用于改进未来的查询。

    Save a learning to improve future troubleshooting queries.
    Use this after discovering patterns, gotchas, or user corrections.

    Args:
        title: 简短标题 / Short title describing the learning
            Example: "defect_types array uses @> operator"
        learning: 学习内容 / The learning content
            Example: "Use defect_types @> ARRAY['披锋'] not IN for array queries"
        learning_type: 学习类型 / Type of learning
            error_pattern: Discovered after fixing an error
            type_gotcha: Data type issue (TEXT vs INTEGER, etc.)
            user_correction: User corrected a wrong assumption
            date_format: Date parsing pattern
        tables_affected: 影响的表（逗号分隔）/ Tables affected (comma-separated)
            Example: "troubleshooting_issues,troubleshooting_cases"

    Returns:
        JSON string confirming the learning was saved

    Examples:
        - save_troubleshooting_learning(
            title="defect_types requires @> operator",
            learning="Use defect_types @> ARRAY['披锋'] for array membership",
            learning_type="type_gotcha",
            tables_affected="troubleshooting_issues"
          )
    """
    try:
        logger.info(f"Saving learning: {title}")

        hybrid_searcher = get_hybrid_searcher()
        if hybrid_searcher is None:
            return json.dumps({
                "error": "Hybrid searcher not available",
            }, ensure_ascii=False)

        # Parse tables_affected
        tables = []
        if tables_affected:
            tables = [t.strip() for t in tables_affected.split(",")]

        # Save using SQL generator's learning method
        hybrid_searcher.sql_generator.save_learning(
            title=title,
            learning=learning,
            learning_type=learning_type,
            tables_affected=tables,
        )

        return json.dumps({
            "status": "success",
            "message": f"Saved learning: {title}",
            "learning_type": learning_type,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Failed to save learning: {e}")
        return json.dumps({
            "error": f"Failed to save learning: {str(e)}",
        }, ensure_ascii=False)


@tool
def learn_troubleshooting_synonym(
    canonical_term: str,
    synonym: str,
    term_type: Literal["defect", "material", "process", "trial", "result"] = "defect",
    confidence: float = 0.8,
) -> str:
    """
    学习新的同义词映射，用于查询扩展。

    Learn a new synonym mapping for query expansion.
    Use this when you discover a term that should map to a standard term.

    Args:
        canonical_term: 标准术语 / The standard/canonical term
            Example: "披锋"
        synonym: 同义词 / The synonym to map
            Example: "毛边"
        term_type: 术语类型 / Type of term
            defect: 缺陷类型 (披锋, 拉白, etc.)
            material: 材料 (HIPS, ABS, etc.)
            process: 工艺 (注塑, 模具, etc.)
            trial: 试模阶段 (T0, T1, T2)
            result: 结果状态 (OK, NG)
        confidence: 置信度 / Confidence in the mapping (0.0-1.0)

    Returns:
        JSON string confirming the synonym was learned

    Examples:
        - learn_troubleshooting_synonym("披锋", "飞边", "defect", 0.9)
        - learn_troubleshooting_synonym("OK", "解决了", "result", 0.8)
    """
    try:
        logger.info(f"Learning synonym: '{synonym}' -> '{canonical_term}'")

        hybrid_searcher = get_hybrid_searcher()
        if hybrid_searcher is None:
            return json.dumps({
                "error": "Hybrid searcher not available",
            }, ensure_ascii=False)

        # Learn the synonym
        hybrid_searcher.expander.learn_synonym(
            canonical_term=canonical_term,
            synonym=synonym,
            term_type=term_type,
            confidence=confidence,
        )

        return json.dumps({
            "status": "success",
            "message": f"Learned: '{synonym}' -> '{canonical_term}'",
            "term_type": term_type,
            "confidence": confidence,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Failed to learn synonym: {e}")
        return json.dumps({
            "error": f"Failed to learn synonym: {str(e)}",
        }, ensure_ascii=False)


# Export tools list for easy import
troubleshooting_tools = [
    search_troubleshooting_kb,
    get_troubleshooting_case_details,
    find_similar_defects,
    # NEW: Structured/Hybrid search tools
    search_troubleshooting_structured,
    save_troubleshooting_learning,
    learn_troubleshooting_synonym,
]


if __name__ == "__main__":
    # Test tools
    print("Testing Troubleshooting Tools")
    print("=" * 70)
    print()

    # Test 1: Search with adaptive mode
    print("Test 1: Searching for '产品披锋' (adaptive mode)")
    print("-" * 70)
    result = search_troubleshooting_kb.invoke({
        "query": "产品披锋",
        "top_k": 5,
        "adaptive": True
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
