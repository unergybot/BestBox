#!/usr/bin/env python3
"""
Adaptive Troubleshooting Searcher

Multi-stage search with LLM-based query classification:
1. Classify query (case-level vs issue-level vs hybrid)
2. Vector search with BGE-M3
3. Rerank with BGE-reranker-v2-m3
4. Metadata boosting

Usage:
    from services.troubleshooting.searcher import TroubleshootingSearcher

    searcher = TroubleshootingSearcher()
    results = searcher.search("产品披锋解决方案", top_k=5)
"""

import sys
import os
from pathlib import Path

# Add project root to path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
import requests
from typing import List, Dict, Literal, Optional
import json
import logging

from services.troubleshooting.embedder import TroubleshootingEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SearchMode = Literal["CASE_LEVEL", "ISSUE_LEVEL", "HYBRID"]


class TroubleshootingSearcher:
    """Adaptive multi-level search for troubleshooting knowledge base"""

    def __init__(
        self,
        llm_url: str = os.getenv("TROUBLESHOOTING_LLM_URL", ""),
        embeddings_url: str = os.getenv(
            "EMBEDDINGS_URL",
            os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
        ),
        reranker_url: str = os.getenv("RERANKER_URL", "http://172.23.0.3:8003"),
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333
    ):
        """Initialize searcher with service URLs"""

        # Normalize defaults from shared env vars
        if not llm_url:
            # LLM_BASE_URL often looks like http://host:port/v1
            llm_base = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
            llm_url = llm_base[:-3] if llm_base.endswith("/v1") else llm_base

        # embeddings service used here expects /health and /embed (no /v1)
        if embeddings_url.endswith("/v1"):
            embeddings_url = embeddings_url[:-3]

        self.llm_url = llm_url
        self.embeddings_url = embeddings_url
        self.reranker_url = reranker_url

        self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedder = TroubleshootingEmbedder(embeddings_url=embeddings_url)

        logger.info("Searcher initialized")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
        classify: bool = True
    ) -> Dict:
        """
        Main search entry point with adaptive routing.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters
            classify: Whether to use LLM classification (disable for testing)

        Returns:
            dict with query, mode, results, total_found
        """
        logger.info(f"🔍 Searching: \"{query}\"")

        # Step 1: Classify query intent (if enabled)
        if classify:
            mode = self._classify_query(query)
        else:
            mode = "ISSUE_LEVEL"  # Default for testing

        logger.info(f"   Mode: {mode}")

        # Step 2: Route to appropriate search strategy
        if mode == "CASE_LEVEL":
            results = self._search_cases(query, top_k, filters)

        elif mode == "ISSUE_LEVEL":
            results = self._search_issues(query, top_k, filters)

        else:  # HYBRID
            case_results = self._search_cases(query, max(1, top_k // 2), filters)
            issue_results = self._search_issues(query, top_k, filters)
            results = self._merge_results(case_results, issue_results, top_k)

        logger.info(f"   Found: {len(results)} results")

        return {
            "query": query,
            "mode": mode,
            "results": results,
            "total_found": len(results)
        }

    def _classify_query(self, query: str) -> SearchMode:
        """
        Use LLM to determine search granularity.

        Args:
            query: User query

        Returns:
            Search mode (CASE_LEVEL, ISSUE_LEVEL, or HYBRID)
        """
        prompt = f"""你是一个搜索意图分类器。分析用户查询并确定搜索粒度。

用户查询: "{query}"

判断标准:
- CASE_LEVEL: 查询整个案件的信息
  例如: "零件1947688的所有问题", "HIPS材料的案例", "2025年9月的案件"

- ISSUE_LEVEL: 查询特定问题或解决方案
  例如: "产品披锋的解决方法", "模具表面污染", "火花纹问题"

- HYBRID: 需要两个层级的信息
  例如: "披锋问题的案例有哪些", "显示所有T1成功的解决方案"

只返回JSON格式，不要其他说明:
{{"mode": "CASE_LEVEL|ISSUE_LEVEL|HYBRID", "confidence": 0.0-1.0, "reasoning": "简短解释"}}"""

        try:
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "qwen3",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 100
                },
                timeout=10
            )

            result = response.json()
            content = result['choices'][0]['message']['content']

            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                classification = json.loads(content[json_start:json_end])
                mode = classification.get('mode', 'ISSUE_LEVEL')

                if mode in ["CASE_LEVEL", "ISSUE_LEVEL", "HYBRID"]:
                    return mode

        except Exception as e:
            logger.warning(f"Query classification failed: {e}, using ISSUE_LEVEL")

        # Fallback to ISSUE_LEVEL (most common)
        return "ISSUE_LEVEL"

    def _search_cases(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Case-level search"""

        # Get query embedding
        query_embedding = self.embedder._get_embedding(query)

        # Build Qdrant filter
        qdrant_filter = self._build_filter(filters) if filters else None

        # Search using query_points
        response = self.qdrant.query_points(
            collection_name="troubleshooting_cases",
            query=query_embedding,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=0.5,
            with_payload=True
        )

        results = response.points

        # Format results
        formatted_results = []
        for hit in results:
            formatted_results.append({
                "type": "case",
                "score": float(hit.score),
                "case_id": hit.payload['case_id'],
                "part_number": hit.payload.get('part_number'),
                "material": hit.payload.get('material'),
                "total_issues": hit.payload.get('total_issues'),
                "source_file": hit.payload.get('source_file'),
                "text_summary": hit.payload.get('text_summary')
            })

        return formatted_results

    def _search_issues(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Issue-level search with reranking"""

        # Stage 1: Vector search (retrieve 3x for reranking)
        query_embedding = self.embedder._get_embedding(query)
        qdrant_filter = self._build_filter(filters) if filters else None

        response = self.qdrant.query_points(
            collection_name="troubleshooting_issues",
            query=query_embedding,
            query_filter=qdrant_filter,
            limit=top_k * 3,
            score_threshold=0.4,
            with_payload=True
        )

        candidates = response.points

        if not candidates:
            return []

        # Stage 2: Rerank (if reranker is available)
        try:
            reranked = self._rerank(query, candidates, top_k)
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, using vector scores")
            reranked = [
                {"score": float(c.score), "payload": c.payload}
                for c in candidates[:top_k]
            ]

        # Stage 3: Metadata boosting (including VLM-aware boosting)
        final_results = []
        query_lower = query.lower()

        for item in reranked:
            score = item['score']
            payload = item['payload']

            # Boost successful solutions
            if payload.get('result_t1') == 'OK' or payload.get('result_t2') == 'OK':
                score *= 1.15

            # Boost if part number mentioned in query
            if payload.get('part_number') and str(payload['part_number']) in query:
                score *= 1.3

            # NEW: VLM-aware boosting
            if payload.get('vlm_processed'):
                # Boost by VLM confidence (max 20% boost at 1.0 confidence)
                vlm_confidence = payload.get('vlm_confidence', 0.0)
                if vlm_confidence > 0:
                    score *= (1 + 0.2 * vlm_confidence)

                # Boost if query matches VLM tags
                for tag in payload.get('tags', []):
                    if tag.lower() in query_lower:
                        score *= 1.1
                        break  # Only apply once

                # Boost high severity issues when query suggests urgency
                severity = payload.get('severity', '').lower()
                urgency_keywords = ['紧急', '严重', 'urgent', 'critical', 'severe']
                if severity == 'high' and any(kw in query_lower for kw in urgency_keywords):
                    score *= 1.2

            final_results.append({
                "type": "issue",
                "score": float(score),
                "issue_id": payload.get('issue_id'),
                "case_id": payload.get('case_id'),
                "part_number": payload.get('part_number'),
                "issue_number": payload.get('issue_number'),
                "trial_version": payload.get('trial_version'),
                "category": payload.get('category'),
                "problem": payload.get('problem'),
                "solution": payload.get('solution'),
                "result_t1": payload.get('result_t1'),
                "result_t2": payload.get('result_t2'),
                "images": payload.get('images', []),
                "defect_types": payload.get('defect_types', []),
                # NEW: Include VLM metadata in results
                "vlm_processed": payload.get('vlm_processed', False),
                "vlm_confidence": payload.get('vlm_confidence', 0.0),
                "severity": payload.get('severity'),
                "tags": payload.get('tags', []),
                "key_insights": payload.get('key_insights', []),
                "suggested_actions": payload.get('suggested_actions', [])
            })

        # Re-sort by boosted scores
        final_results.sort(key=lambda x: x['score'], reverse=True)

        # Deduplicate by issue_id, keeping highest scoring entry
        seen_issue_ids = set()
        deduped_results = []
        for result in final_results:
            issue_id = result.get('issue_id')
            if issue_id and issue_id not in seen_issue_ids:
                seen_issue_ids.add(issue_id)
                deduped_results.append(result)
            elif not issue_id:
                deduped_results.append(result)

        return deduped_results[:top_k]

    def _rerank(self, query: str, candidates: List, top_k: int) -> List:
        """Rerank candidates using BGE-reranker-v2-m3"""

        # Prepare documents for reranking
        documents = []
        for candidate in candidates:
            # Combine text fields
            doc_text = f"{candidate.payload.get('problem', '')} {candidate.payload.get('solution', '')}"

            # Add image descriptions if available
            for img in candidate.payload.get('images', []):
                if img.get('vl_description'):
                    doc_text += f" {img['vl_description']}"

            documents.append(doc_text)

        # Call reranker service
        response = requests.post(
            f"{self.reranker_url}/rerank",
            json={
                "query": query,
                "passages": documents
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        # Map back to candidates using correct reranker response format
        reranked = []
        for idx, score in zip(data['ranked_indices'], data['scores']):
            reranked.append({
                "score": score,
                "payload": candidates[idx].payload
            })

        return reranked

    def _merge_results(
        self,
        case_results: List[Dict],
        issue_results: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """Merge and deduplicate case + issue results"""

        # Combine results with type marker
        all_results = case_results + issue_results

        # Sort by score
        all_results.sort(key=lambda x: x['score'], reverse=True)

        # Return top_k
        return all_results[:top_k]

    def _build_filter(self, filters: Dict) -> Filter:
        """Build Qdrant filter from dict"""

        conditions = []

        if 'part_number' in filters:
            conditions.append(
                FieldCondition(
                    key="part_number",
                    match=MatchValue(value=filters['part_number'])
                )
            )

        if 'trial_version' in filters:
            conditions.append(
                FieldCondition(
                    key="trial_version",
                    match=MatchValue(value=filters['trial_version'])
                )
            )

        if 'result' in filters:
            # Match either result_t1 or result_t2
            conditions.append(
                FieldCondition(
                    key="result_t1",
                    match=MatchValue(value=filters['result'])
                )
            )

        return Filter(must=conditions) if conditions else None


if __name__ == "__main__":
    # Test search
    print("Testing Troubleshooting Searcher")
    print("=" * 70)
    print()

    searcher = TroubleshootingSearcher()

    # Test queries
    test_queries = [
        "产品披锋",
        "模具表面污染问题",
        "零件1947688",
    ]

    for query in test_queries:
        print(f"Query: \"{query}\"")
        print("-" * 70)

        results = searcher.search(query, top_k=3, classify=False)

        print(f"Mode: {results['mode']}")
        print(f"Found: {results['total_found']} results\n")

        for i, result in enumerate(results['results'][:2], 1):
            print(f"{i}. [{result['type']}] Score: {result['score']:.3f}")
            if result['type'] == 'issue':
                print(f"   Problem: {result['problem'][:60]}...")
                print(f"   Solution: {result['solution'][:60]}...")
            else:
                print(f"   Case: {result['case_id']}")
            print()

        print()
