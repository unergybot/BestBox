#!/usr/bin/env python3
"""
Hybrid Searcher for Troubleshooting

Orchestrates SQL (structured) and Qdrant (semantic) search with result fusion.

Architecture:
    User Query
        │
        ▼
    Query Expander (ASR cleanup, synonyms, intent classification)
        │
        ├── STRUCTURED ──► Text-to-SQL ──► PostgreSQL
        │
        ├── SEMANTIC ────► Qdrant Vector Search (existing)
        │
        └── HYBRID ──────► Both + Reciprocal Rank Fusion (RRF)

Usage:
    from services.troubleshooting.hybrid_searcher import HybridSearcher

    searcher = HybridSearcher()
    results = searcher.search("HIPS材料的披锋怎么解决")
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
import logging

# Add project root to path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

import psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.troubleshooting.query_expander import QueryExpander
from services.troubleshooting.text_to_sql import TextToSQLGenerator
from services.troubleshooting.searcher import TroubleshootingSearcher
from services.troubleshooting.cache import TroubleshootingCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SearchMode = Literal["STRUCTURED", "SEMANTIC", "HYBRID", "AUTO"]


class HybridSearcher:
    """Hybrid search combining SQL and vector search."""

    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_database: str = "bestbox",
        pg_user: str = "bestbox",
        pg_password: str = "bestbox",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        llm_url: Optional[str] = None,
        embeddings_url: Optional[str] = None,
    ):
        """
        Initialize hybrid searcher.

        Args:
            pg_host: PostgreSQL host
            pg_port: PostgreSQL port
            pg_database: PostgreSQL database
            pg_user: PostgreSQL user
            pg_password: PostgreSQL password
            qdrant_host: Qdrant host
            qdrant_port: Qdrant port
            llm_url: LLM service URL
            embeddings_url: Embeddings service URL
        """
        self.pg_params = {
            "host": os.getenv("POSTGRES_HOST", pg_host),
            "port": int(os.getenv("POSTGRES_PORT", pg_port)),
            "database": os.getenv("POSTGRES_DB", pg_database),
            "user": os.getenv("POSTGRES_USER", pg_user),
            "password": os.getenv("POSTGRES_PASSWORD", pg_password),
        }

        # Initialize components
        self.expander = QueryExpander(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
            llm_url=llm_url,
        )

        self.sql_generator = TextToSQLGenerator(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
            llm_url=llm_url,
        )

        self.semantic_searcher = TroubleshootingSearcher(
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port,
            llm_url=llm_url or os.getenv("LLM_BASE_URL", "http://localhost:8001"),
            embeddings_url=embeddings_url
            or os.getenv("EMBEDDINGS_URL", "http://localhost:8004"),
        )

        # Initialize cache for search results (5-min TTL)
        self.cache = TroubleshootingCache()

        logger.info("HybridSearcher initialized (with caching)")

    def search(
        self,
        query: str,
        mode: SearchMode = "AUTO",
        top_k: int = 10,
        filters: Optional[Dict] = None,
        return_sql: bool = False,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform hybrid search.

        Args:
            query: User query
            mode: Search mode (AUTO, STRUCTURED, SEMANTIC, HYBRID)
            top_k: Number of results to return
            filters: Optional filters (part_number, material, etc.)
            return_sql: Include generated SQL in response
            use_cache: Whether to use result caching (default: True)

        Returns:
            Dict with results, mode, query expansion info
        """
        logger.info(f"🔍 Hybrid search: \"{query}\" (mode={mode})")

        # Check cache first (saves 200-500ms on cache hit)
        if use_cache:
            cached = self.cache.get_search_results(
                query=query,
                mode=mode,
                filters=filters,
                top_k=top_k,
            )
            if cached:
                logger.info(f"   Cache HIT for query")
                return cached

        # Step 1: Expand query (ASR cleanup, synonyms, intent classification)
        expansion = self.expander.expand(query)
        expanded_query = expansion["expanded"]
        detected_intent = expansion["intent"]

        # Step 2: Determine search mode
        if mode == "AUTO":
            mode = detected_intent

        logger.info(f"   Intent: {detected_intent}, Mode: {mode}")

        # Step 3: Execute search based on mode
        if mode == "STRUCTURED":
            results = self._search_structured(expanded_query, top_k, filters)
        elif mode == "SEMANTIC":
            results = self._search_semantic(expanded_query, top_k, filters)
        else:  # HYBRID
            results = self._search_hybrid(expanded_query, top_k, filters)

        # Step 4: Build response
        response = {
            "query": query,
            "expanded_query": expanded_query,
            "mode": mode,
            "intent_confidence": expansion["confidence"],
            "synonyms_used": expansion["synonyms_used"],
            "total_found": len(results.get("results", [])),
            "results": results.get("results", []),
        }

        if return_sql and results.get("sql"):
            response["generated_sql"] = results["sql"]

        if results.get("error"):
            response["error"] = results["error"]

        # Cache the response (5-min TTL)
        if use_cache and not results.get("error"):
            self.cache.set_search_results(
                query=query,
                mode=mode,
                results=response,
                filters=filters,
                top_k=top_k,
            )

        return response

    def _search_structured(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute structured SQL search."""
        # Generate SQL
        sql_result = self.sql_generator.generate(query)

        if not sql_result["valid"]:
            logger.warning(f"SQL generation failed: {sql_result['error']}")
            # Fallback to semantic search
            return self._search_semantic(query, top_k, filters)

        sql = sql_result["sql"]

        # Apply additional filters if provided
        if filters:
            sql = self._apply_sql_filters(sql, filters)

        # Execute SQL
        exec_result = self.sql_generator.execute(sql, limit=top_k)

        if exec_result.get("error"):
            logger.warning(f"SQL execution failed: {exec_result['error']}")
            return {"error": exec_result["error"], "sql": sql, "results": []}

        # Format results
        results = self._format_sql_results(exec_result, sql_result["tables_used"])

        return {
            "sql": sql,
            "results": results,
            "total_count": exec_result.get("total_count", len(results)),
        }

    def _search_semantic(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute semantic vector search."""
        search_result = self.semantic_searcher.search(
            query=query,
            top_k=top_k,
            filters=filters,
            classify=False,  # We already classified
            adaptive=True,
        )

        # Convert to common format
        results = []
        for item in search_result.get("results", []):
            results.append({
                "source": "semantic",
                "score": item.get("score", 0),
                "type": item.get("type", "issue"),
                **item,
            })

        return {"results": results}

    def _search_hybrid(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Execute hybrid search with result fusion.

        Runs SQL and semantic searches in parallel using ThreadPoolExecutor.
        This saves 100-300ms compared to sequential execution.
        """
        structured_results = {}
        semantic_results = {}

        # Execute both searches in parallel for faster response
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both searches
            structured_future = executor.submit(
                self._search_structured, query, top_k * 2, filters
            )
            semantic_future = executor.submit(
                self._search_semantic, query, top_k * 2, filters
            )

            # Collect results as they complete
            for future in as_completed([structured_future, semantic_future]):
                try:
                    if future == structured_future:
                        structured_results = future.result()
                    else:
                        semantic_results = future.result()
                except Exception as e:
                    logger.warning(f"Parallel search task failed: {e}")
                    # Continue with partial results

        # Fuse results using Reciprocal Rank Fusion (RRF)
        fused = self._reciprocal_rank_fusion(
            structured_results.get("results", []),
            semantic_results.get("results", []),
            k=60,  # RRF constant
        )

        return {
            "sql": structured_results.get("sql"),
            "results": fused[:top_k],
        }

    def _reciprocal_rank_fusion(
        self,
        results_a: List[Dict],
        results_b: List[Dict],
        k: int = 60,
    ) -> List[Dict]:
        """
        Fuse two result sets using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) for each result list

        Args:
            results_a: First result set
            results_b: Second result set
            k: Ranking constant (default 60)

        Returns:
            Fused and sorted results
        """
        scores = {}

        # Score results from list A
        for rank, result in enumerate(results_a, 1):
            key = self._get_result_key(result)
            scores[key] = scores.get(key, {"result": result, "score": 0})
            scores[key]["score"] += 1 / (k + rank)
            scores[key]["result"]["sources"] = scores[key]["result"].get("sources", [])
            if "structured" not in scores[key]["result"]["sources"]:
                scores[key]["result"]["sources"].append("structured")

        # Score results from list B
        for rank, result in enumerate(results_b, 1):
            key = self._get_result_key(result)
            if key in scores:
                scores[key]["score"] += 1 / (k + rank)
                if "semantic" not in scores[key]["result"]["sources"]:
                    scores[key]["result"]["sources"].append("semantic")
            else:
                scores[key] = {
                    "result": result,
                    "score": 1 / (k + rank),
                }
                scores[key]["result"]["sources"] = ["semantic"]

        # Sort by fused score
        fused = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

        # Update results with fused score
        for item in fused:
            item["result"]["fusion_score"] = item["score"]

        return [item["result"] for item in fused]

    def _get_result_key(self, result: Dict) -> str:
        """Get unique key for a result (for deduplication)."""
        if result.get("issue_id"):
            return result["issue_id"]
        elif result.get("case_id"):
            return result["case_id"]
        else:
            # Fallback to problem text hash
            return str(hash(result.get("problem", str(result))))

    def _format_sql_results(
        self, exec_result: Dict, tables_used: List[str]
    ) -> List[Dict]:
        """Format SQL results to common format."""
        results = []
        columns = exec_result.get("columns", [])
        rows = exec_result.get("rows", [])

        for row in rows:
            result = {"source": "structured", "type": "sql_row"}

            # Map columns to result
            for i, col in enumerate(columns):
                if i < len(row):
                    result[col] = row[i]

            # Determine type based on content
            if "issue_id" in result:
                result["type"] = "issue"
            elif "case_id" in result and "issue_id" not in result:
                result["type"] = "case"
            elif "count" in result or any("count" in str(c).lower() for c in columns):
                result["type"] = "aggregation"

            results.append(result)

        return results

    def _apply_sql_filters(self, sql: str, filters: Dict) -> str:
        """Apply additional filters to SQL query."""
        # Find WHERE clause or add one
        sql_upper = sql.upper()

        conditions = []
        if filters.get("part_number"):
            conditions.append(f"part_number = '{filters['part_number']}'")
        if filters.get("material"):
            conditions.append(f"material ILIKE '%{filters['material']}%'")
        if filters.get("trial_version"):
            conditions.append(f"trial_version = '{filters['trial_version']}'")

        if not conditions:
            return sql

        filter_clause = " AND ".join(conditions)

        if "WHERE" in sql_upper:
            # Add to existing WHERE
            where_idx = sql_upper.index("WHERE")
            sql = sql[:where_idx + 5] + f" ({filter_clause}) AND " + sql[where_idx + 6:]
        else:
            # Add WHERE before ORDER BY, GROUP BY, or LIMIT
            for keyword in ["ORDER BY", "GROUP BY", "LIMIT"]:
                if keyword in sql_upper:
                    idx = sql_upper.index(keyword)
                    sql = sql[:idx] + f" WHERE {filter_clause} " + sql[idx:]
                    break
            else:
                # No modifier, add at end
                sql = sql.rstrip(";") + f" WHERE {filter_clause}"

        return sql

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def search_structured(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Force structured (SQL) search."""
        return self.search(query, mode="STRUCTURED", top_k=top_k, filters=filters, return_sql=True)

    def search_semantic(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Force semantic (vector) search."""
        return self.search(query, mode="SEMANTIC", top_k=top_k, filters=filters)

    def search_hybrid(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Force hybrid search."""
        return self.search(query, mode="HYBRID", top_k=top_k, filters=filters, return_sql=True)

    # ========================================================================
    # Query Logging
    # ========================================================================

    def log_query(
        self,
        original_query: str,
        expanded_query: str,
        intent: str,
        sql: Optional[str],
        result_count: int,
        execution_time_ms: int,
        user_feedback: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Log a query for analysis and improvement."""
        try:
            conn = psycopg2.connect(**self.pg_params)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ts_query_log
                    (original_query, expanded_query, intent_classification,
                     generated_sql, result_count, execution_time_ms,
                     user_feedback, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        original_query,
                        expanded_query,
                        intent,
                        sql,
                        result_count,
                        execution_time_ms,
                        user_feedback,
                        session_id,
                    ),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to log query: {e}")


if __name__ == "__main__":
    # Test hybrid search
    print("Testing Hybrid Searcher")
    print("=" * 70)
    print()

    searcher = HybridSearcher()

    test_queries = [
        ("有多少个披锋问题", "STRUCTURED"),
        ("披锋怎么解决", "SEMANTIC"),
        ("HIPS材料的披锋解决方案", "HYBRID"),
        ("毛边问题有哪些", "AUTO"),  # Should detect and route
    ]

    for query, mode in test_queries:
        print(f"Query: \"{query}\" (mode={mode})")
        print("-" * 70)

        result = searcher.search(query, mode=mode, top_k=3, return_sql=True)

        print(f"  Mode used: {result['mode']}")
        print(f"  Expanded: {result['expanded_query']}")
        print(f"  Confidence: {result['intent_confidence']}")
        print(f"  Found: {result['total_found']} results")

        if result.get("generated_sql"):
            print(f"  SQL: {result['generated_sql'][:100]}...")

        if result.get("synonyms_used"):
            print(f"  Synonyms: {result['synonyms_used']}")

        if result["results"]:
            print(f"  Top result: {result['results'][0].get('problem', result['results'][0])[:60]}...")

        print()
