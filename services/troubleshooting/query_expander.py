#!/usr/bin/env python3
"""
Query Expander for Troubleshooting Text-to-SQL

Handles:
1. ASR artifact cleaning (filler words, repeated chars)
2. Synonym expansion from database
3. Intent classification (STRUCTURED vs SEMANTIC vs HYBRID)

Usage:
    from services.troubleshooting.query_expander import QueryExpander

    expander = QueryExpander()
    result = expander.expand("毛边问题有多少个")
    # result = {
    #     "original": "毛边问题有多少个",
    #     "cleaned": "毛边问题有多少个",
    #     "expanded": "披锋问题有多少个",
    #     "intent": "STRUCTURED",
    #     "synonyms_used": [{"毛边": "披锋"}],
    #     "confidence": 0.9
    # }
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
import logging

# Add project root to path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

import psycopg2
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IntentType = Literal["STRUCTURED", "SEMANTIC", "HYBRID"]


class QueryExpander:
    """Expand and classify troubleshooting queries."""

    # Keywords that indicate structured queries (SQL-friendly)
    STRUCTURED_KEYWORDS = {
        # Counting
        "多少", "几个", "数量", "总数", "统计", "count",
        # Filtering
        "成功", "失败", "T1", "T2", "T0", "OK", "NG",
        # Aggregation
        "分布", "占比", "比例", "百分比", "排名", "top",
        # Comparison
        "最多", "最少", "最高", "最低", "平均",
        # Listing with filters
        "列出", "显示", "有哪些",
    }

    # Keywords that indicate semantic queries (vector search)
    SEMANTIC_KEYWORDS = {
        "怎么", "如何", "为什么", "原因", "方法", "方案",
        "解决", "处理", "改善", "优化",
        "类似", "相似", "相关",
        "建议", "推荐",
    }

    # ASR filler words to remove
    ASR_FILLERS = [
        "嗯", "啊", "呃", "那个", "就是", "然后",
        "这个", "那", "哦", "噢", "额",
    ]

    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_database: str = "bestbox",
        pg_user: str = "bestbox",
        pg_password: str = "bestbox",
        llm_url: Optional[str] = None,
    ):
        """
        Initialize query expander.

        Args:
            pg_host: PostgreSQL host
            pg_port: PostgreSQL port
            pg_database: PostgreSQL database
            pg_user: PostgreSQL user
            pg_password: PostgreSQL password
            llm_url: LLM service URL for fallback classification
        """
        self.pg_params = {
            "host": os.getenv("POSTGRES_HOST", pg_host),
            "port": int(os.getenv("POSTGRES_PORT", pg_port)),
            "database": os.getenv("POSTGRES_DB", pg_database),
            "user": os.getenv("POSTGRES_USER", pg_user),
            "password": os.getenv("POSTGRES_PASSWORD", pg_password),
        }

        # LLM for fallback classification
        if llm_url:
            self.llm_url = llm_url
        else:
            llm_base = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")
            self.llm_url = llm_base[:-3] if llm_base.endswith("/v1") else llm_base

        # Cache synonyms in memory for fast lookup
        self._synonym_cache: Dict[str, str] = {}
        self._cache_loaded = False

        logger.info("QueryExpander initialized")

    def _get_pg_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(**self.pg_params)

    def _load_synonym_cache(self):
        """Load all synonyms into memory cache."""
        if self._cache_loaded:
            return

        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT synonym, canonical_term, confidence
                    FROM troubleshooting_synonyms
                    ORDER BY confidence DESC
                    """
                )
                for row in cur.fetchall():
                    synonym, canonical, confidence = row
                    # Only cache if not already present (higher confidence first)
                    if synonym not in self._synonym_cache:
                        self._synonym_cache[synonym] = canonical

            conn.close()
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._synonym_cache)} synonyms into cache")
        except Exception as e:
            logger.warning(f"Failed to load synonym cache: {e}")

    def expand(self, query: str) -> Dict:
        """
        Expand and classify a query.

        Args:
            query: Raw user query (possibly from ASR)

        Returns:
            Dict with expansion results
        """
        # Step 1: Clean ASR artifacts
        cleaned = self._clean_asr(query)

        # Step 2: Expand synonyms
        expanded, synonyms_used = self._expand_synonyms(cleaned)

        # Step 3: Classify intent
        intent, confidence = self._classify_intent(expanded)

        return {
            "original": query,
            "cleaned": cleaned,
            "expanded": expanded,
            "intent": intent,
            "synonyms_used": synonyms_used,
            "confidence": confidence,
        }

    def _clean_asr(self, query: str) -> str:
        """
        Clean ASR artifacts from query.

        Handles:
        - Filler words (嗯, 啊, 那个)
        - Repeated characters (我我我想)
        - Extra whitespace
        """
        q = query.strip()
        if not q:
            return q

        # Remove filler words
        for filler in self.ASR_FILLERS:
            q = q.replace(filler, "")

        # Remove repeated characters (Chinese)
        # Match same char repeated 3+ times, replace with 1
        q = re.sub(r'(.)\1{2,}', r'\1', q)

        # Remove repeated words (Chinese 2-char words)
        q = re.sub(r'(\S{2})\1+', r'\1', q)

        # Normalize whitespace
        q = re.sub(r'\s+', ' ', q).strip()

        return q

    def _expand_synonyms(self, query: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Expand synonyms in query using database mappings.

        Args:
            query: Cleaned query

        Returns:
            Tuple of (expanded query, list of synonym mappings used)
        """
        self._load_synonym_cache()

        expanded = query
        synonyms_used = []

        # Sort synonyms by length (longest first) to avoid partial replacements
        sorted_synonyms = sorted(
            self._synonym_cache.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

        for synonym, canonical in sorted_synonyms:
            if synonym in expanded and synonym != canonical:
                expanded = expanded.replace(synonym, canonical)
                synonyms_used.append({synonym: canonical})
                logger.debug(f"Expanded '{synonym}' -> '{canonical}'")

        return expanded, synonyms_used

    def _classify_intent(self, query: str) -> Tuple[IntentType, float]:
        """
        Classify query intent using keyword matching with LLM fallback.

        Args:
            query: Expanded query

        Returns:
            Tuple of (intent type, confidence)
        """
        query_lower = query.lower()

        # Count keyword matches
        structured_count = sum(1 for kw in self.STRUCTURED_KEYWORDS if kw in query_lower)
        semantic_count = sum(1 for kw in self.SEMANTIC_KEYWORDS if kw in query_lower)

        # Clear winner
        if structured_count > 0 and semantic_count == 0:
            return "STRUCTURED", 0.9

        if semantic_count > 0 and structured_count == 0:
            return "SEMANTIC", 0.9

        # Both or neither - could be hybrid
        if structured_count > 0 and semantic_count > 0:
            return "HYBRID", 0.8

        # No clear keywords - use LLM fallback
        return self._classify_with_llm(query)

    def _classify_with_llm(self, query: str) -> Tuple[IntentType, float]:
        """
        Use LLM for intent classification fallback.

        Args:
            query: Query to classify

        Returns:
            Tuple of (intent type, confidence)
        """
        prompt = f"""你是一个查询意图分类器。分析用户的故障排除查询并确定最佳搜索策略。

用户查询: "{query}"

分类标准:
- STRUCTURED: 需要精确过滤、计数、聚合的查询
  例如: "有多少个披锋问题", "T1成功的案例", "HIPS材料的问题数量"

- SEMANTIC: 需要语义理解、相似度搜索的查询
  例如: "披锋怎么解决", "拉白的原因是什么", "类似的问题有哪些"

- HYBRID: 需要结构化过滤 + 语义搜索的查询
  例如: "HIPS材料的披锋解决方案", "T1失败的问题怎么改善"

只返回JSON格式:
{{"intent": "STRUCTURED|SEMANTIC|HYBRID", "confidence": 0.0-1.0, "reasoning": "简短解释"}}"""

        try:
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "qwen3",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 100,
                },
                timeout=10,
            )

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Extract JSON from response
            import json
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                classification = json.loads(content[json_start:json_end])
                intent = classification.get("intent", "SEMANTIC")
                confidence = classification.get("confidence", 0.7)

                if intent in ["STRUCTURED", "SEMANTIC", "HYBRID"]:
                    return intent, confidence

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")

        # Default to SEMANTIC (vector search)
        return "SEMANTIC", 0.5

    def get_canonical_term(self, term: str) -> Optional[str]:
        """
        Get the canonical term for a synonym.

        Args:
            term: Term to look up

        Returns:
            Canonical term or None if not found
        """
        self._load_synonym_cache()
        return self._synonym_cache.get(term)

    def get_all_synonyms(self, canonical_term: str) -> List[str]:
        """
        Get all synonyms for a canonical term.

        Args:
            canonical_term: The standard term

        Returns:
            List of synonyms including the canonical term itself
        """
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT synonym FROM troubleshooting_synonyms
                    WHERE canonical_term = %s
                    """,
                    (canonical_term,),
                )
                synonyms = [row[0] for row in cur.fetchall()]
            conn.close()

            # Include the canonical term itself
            if canonical_term not in synonyms:
                synonyms.insert(0, canonical_term)

            return synonyms
        except Exception as e:
            logger.error(f"Failed to get synonyms: {e}")
            return [canonical_term]

    def record_synonym_usage(self, synonym: str):
        """
        Record that a synonym was used (for analytics).

        Args:
            synonym: The synonym that was used
        """
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE troubleshooting_synonyms
                    SET usage_count = usage_count + 1, last_used_at = NOW()
                    WHERE synonym = %s
                    """,
                    (synonym,),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to record synonym usage: {e}")

    def learn_synonym(
        self,
        canonical_term: str,
        synonym: str,
        term_type: str = "defect",
        confidence: float = 0.8,
    ):
        """
        Learn a new synonym mapping.

        Args:
            canonical_term: The standard term
            synonym: The new synonym
            term_type: Type of term (defect, material, process, etc.)
            confidence: Confidence in the mapping (0.0-1.0)
        """
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO troubleshooting_synonyms
                    (canonical_term, synonym, term_type, confidence, source)
                    VALUES (%s, %s, %s, %s, 'learned')
                    ON CONFLICT (canonical_term, synonym) DO UPDATE
                    SET confidence = GREATEST(troubleshooting_synonyms.confidence, EXCLUDED.confidence),
                        usage_count = troubleshooting_synonyms.usage_count + 1
                    """,
                    (canonical_term, synonym, term_type, confidence),
                )
            conn.commit()
            conn.close()

            # Update cache
            self._synonym_cache[synonym] = canonical_term
            logger.info(f"Learned synonym: '{synonym}' -> '{canonical_term}'")
        except Exception as e:
            logger.error(f"Failed to learn synonym: {e}")

    def refresh_cache(self):
        """Force refresh of synonym cache."""
        self._cache_loaded = False
        self._synonym_cache.clear()
        self._load_synonym_cache()


if __name__ == "__main__":
    # Test query expansion
    print("Testing Query Expander")
    print("=" * 70)
    print()

    expander = QueryExpander()

    test_queries = [
        "毛边问题有多少个",  # Synonym + STRUCTURED
        "披锋怎么解决",  # SEMANTIC
        "HIPS材料的毛刺解决方案",  # Synonym + HYBRID
        "T1成功的案例",  # STRUCTURED
        "嗯那个我想问下毛边问题",  # ASR cleanup + Synonym
        "有多少个T1失败的问题",  # STRUCTURED
        "拉白的原因是什么",  # SEMANTIC
    ]

    for query in test_queries:
        print(f"Query: \"{query}\"")
        print("-" * 70)

        result = expander.expand(query)

        print(f"  Cleaned:  {result['cleaned']}")
        print(f"  Expanded: {result['expanded']}")
        print(f"  Intent:   {result['intent']} (confidence: {result['confidence']})")
        if result["synonyms_used"]:
            print(f"  Synonyms: {result['synonyms_used']}")
        print()
