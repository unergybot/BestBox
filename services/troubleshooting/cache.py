#!/usr/bin/env python3
"""
Redis Caching Layer for Troubleshooting Search

Provides caching for:
- Query embeddings (TTL: 24 hours) - Embeddings are deterministic
- Search results (TTL: 5 minutes) - Balance freshness vs speed
- Reranker scores (TTL: 1 hour) - Stable for similar queries

Usage:
    from services.troubleshooting.cache import TroubleshootingCache

    cache = TroubleshootingCache()

    # Cache embedding
    embedding = cache.get_embedding("披锋问题")
    if embedding is None:
        embedding = embedder.embed("披锋问题")
        cache.set_embedding("披锋问题", embedding)

    # Cache search results
    results = cache.get_search_results("披锋问题", mode="SEMANTIC")
    if results is None:
        results = searcher.search("披锋问题")
        cache.set_search_results("披锋问题", mode="SEMANTIC", results=results)
"""

import os
import json
import hashlib
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TroubleshootingCache:
    """
    Redis-backed cache for troubleshooting search components.

    Caches embeddings, search results, and reranker scores to reduce
    latency on repeated or similar queries.
    """

    # TTL values in seconds
    EMBEDDING_TTL = 24 * 60 * 60  # 24 hours (embeddings are deterministic)
    SEARCH_RESULT_TTL = 5 * 60     # 5 minutes (balance freshness vs speed)
    RERANK_SCORE_TTL = 60 * 60     # 1 hour (stable for similar queries)

    # Key prefixes
    PREFIX_EMBEDDING = "ts:emb:"
    PREFIX_SEARCH = "ts:search:"
    PREFIX_RERANK = "ts:rerank:"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        enabled: bool = True,
    ):
        """
        Initialize cache.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var.
            enabled: Whether caching is enabled. Set to False for testing.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/2")
        self.enabled = enabled and REDIS_AVAILABLE
        self._redis: Optional["redis.Redis"] = None
        self._stats = {
            "embedding_hits": 0,
            "embedding_misses": 0,
            "search_hits": 0,
            "search_misses": 0,
            "rerank_hits": 0,
            "rerank_misses": 0,
        }

        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, caching disabled. Install with: pip install redis")
        elif self.enabled:
            logger.info(f"TroubleshootingCache initialized (redis={self.redis_url})")

    def _get_redis(self) -> Optional["redis.Redis"]:
        """Get or create Redis connection."""
        if not self.enabled or not REDIS_AVAILABLE:
            return None

        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # Handle bytes for embeddings
                )
                # Test connection
                self._redis.ping()
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self.enabled = False
                return None

        return self._redis

    @staticmethod
    def _hash_key(text: str) -> str:
        """Generate MD5 hash of text for cache key."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_params(params: Dict[str, Any]) -> str:
        """Generate hash of parameters dict for cache key."""
        # Sort keys for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True)
        return hashlib.md5(sorted_params.encode("utf-8")).hexdigest()

    # ========================================================================
    # Embedding Cache (TTL: 24 hours)
    # ========================================================================

    def get_embedding(self, query: str) -> Optional[List[float]]:
        """
        Get cached embedding for query.

        Args:
            query: Query text

        Returns:
            Embedding vector if cached, None otherwise
        """
        r = self._get_redis()
        if not r:
            return None

        key = f"{self.PREFIX_EMBEDDING}{self._hash_key(query)}"

        try:
            data = r.get(key)
            if data:
                self._stats["embedding_hits"] += 1
                return json.loads(data)
            self._stats["embedding_misses"] += 1
            return None
        except Exception as e:
            logger.warning(f"Cache get_embedding failed: {e}")
            return None

    def set_embedding(self, query: str, embedding: List[float]) -> bool:
        """
        Cache embedding for query.

        Args:
            query: Query text
            embedding: Embedding vector

        Returns:
            True if cached successfully
        """
        r = self._get_redis()
        if not r:
            return False

        key = f"{self.PREFIX_EMBEDDING}{self._hash_key(query)}"

        try:
            r.set(key, json.dumps(embedding), ex=self.EMBEDDING_TTL)
            return True
        except Exception as e:
            logger.warning(f"Cache set_embedding failed: {e}")
            return False

    # ========================================================================
    # Search Result Cache (TTL: 5 minutes)
    # ========================================================================

    def get_search_results(
        self,
        query: str,
        mode: str,
        filters: Optional[Dict] = None,
        top_k: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached search results.

        Args:
            query: Query text
            mode: Search mode (STRUCTURED, SEMANTIC, HYBRID)
            filters: Optional filters
            top_k: Number of results

        Returns:
            Cached results dict if found, None otherwise
        """
        r = self._get_redis()
        if not r:
            return None

        params = {"query": query, "mode": mode, "filters": filters, "top_k": top_k}
        key = f"{self.PREFIX_SEARCH}{self._hash_params(params)}"

        try:
            data = r.get(key)
            if data:
                self._stats["search_hits"] += 1
                result = json.loads(data)
                result["_cached"] = True
                result["_cache_key"] = key
                return result
            self._stats["search_misses"] += 1
            return None
        except Exception as e:
            logger.warning(f"Cache get_search_results failed: {e}")
            return None

    def set_search_results(
        self,
        query: str,
        mode: str,
        results: Dict[str, Any],
        filters: Optional[Dict] = None,
        top_k: int = 10,
    ) -> bool:
        """
        Cache search results.

        Args:
            query: Query text
            mode: Search mode
            results: Search results dict
            filters: Optional filters
            top_k: Number of results

        Returns:
            True if cached successfully
        """
        r = self._get_redis()
        if not r:
            return False

        params = {"query": query, "mode": mode, "filters": filters, "top_k": top_k}
        key = f"{self.PREFIX_SEARCH}{self._hash_params(params)}"

        try:
            # Add cache metadata
            cache_data = dict(results)
            cache_data["_cached_at"] = datetime.utcnow().isoformat()
            r.set(key, json.dumps(cache_data), ex=self.SEARCH_RESULT_TTL)
            return True
        except Exception as e:
            logger.warning(f"Cache set_search_results failed: {e}")
            return False

    # ========================================================================
    # Reranker Score Cache (TTL: 1 hour)
    # ========================================================================

    def get_rerank_scores(
        self,
        query: str,
        doc_ids: List[str],
    ) -> Optional[Dict[str, float]]:
        """
        Get cached reranker scores.

        Args:
            query: Query text
            doc_ids: List of document IDs

        Returns:
            Dict mapping doc_id -> score if cached, None otherwise
        """
        r = self._get_redis()
        if not r:
            return None

        params = {"query": query, "doc_ids": sorted(doc_ids)}
        key = f"{self.PREFIX_RERANK}{self._hash_params(params)}"

        try:
            data = r.get(key)
            if data:
                self._stats["rerank_hits"] += 1
                return json.loads(data)
            self._stats["rerank_misses"] += 1
            return None
        except Exception as e:
            logger.warning(f"Cache get_rerank_scores failed: {e}")
            return None

    def set_rerank_scores(
        self,
        query: str,
        doc_ids: List[str],
        scores: Dict[str, float],
    ) -> bool:
        """
        Cache reranker scores.

        Args:
            query: Query text
            doc_ids: List of document IDs
            scores: Dict mapping doc_id -> score

        Returns:
            True if cached successfully
        """
        r = self._get_redis()
        if not r:
            return False

        params = {"query": query, "doc_ids": sorted(doc_ids)}
        key = f"{self.PREFIX_RERANK}{self._hash_params(params)}"

        try:
            r.set(key, json.dumps(scores), ex=self.RERANK_SCORE_TTL)
            return True
        except Exception as e:
            logger.warning(f"Cache set_rerank_scores failed: {e}")
            return False

    # ========================================================================
    # Cache Management
    # ========================================================================

    def invalidate_search_cache(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate search result cache entries.

        Args:
            pattern: Optional pattern to match (e.g., "*披锋*")

        Returns:
            Number of keys deleted
        """
        r = self._get_redis()
        if not r:
            return 0

        try:
            if pattern:
                # Delete specific pattern (requires SCAN)
                cursor = 0
                deleted = 0
                while True:
                    cursor, keys = r.scan(cursor, match=f"{self.PREFIX_SEARCH}*")
                    if keys:
                        r.delete(*keys)
                        deleted += len(keys)
                    if cursor == 0:
                        break
                return deleted
            else:
                # Delete all search cache
                cursor = 0
                deleted = 0
                while True:
                    cursor, keys = r.scan(cursor, match=f"{self.PREFIX_SEARCH}*")
                    if keys:
                        r.delete(*keys)
                        deleted += len(keys)
                    if cursor == 0:
                        break
                logger.info(f"Invalidated {deleted} search cache entries")
                return deleted
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hit/miss counts and hit rates
        """
        stats = dict(self._stats)

        # Calculate hit rates
        emb_total = stats["embedding_hits"] + stats["embedding_misses"]
        search_total = stats["search_hits"] + stats["search_misses"]
        rerank_total = stats["rerank_hits"] + stats["rerank_misses"]

        stats["embedding_hit_rate"] = (
            stats["embedding_hits"] / emb_total if emb_total > 0 else 0.0
        )
        stats["search_hit_rate"] = (
            stats["search_hits"] / search_total if search_total > 0 else 0.0
        )
        stats["rerank_hit_rate"] = (
            stats["rerank_hits"] / rerank_total if rerank_total > 0 else 0.0
        )

        return stats

    def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            self._redis.close()
            self._redis = None


# Global cache instance (singleton)
_cache_instance: Optional[TroubleshootingCache] = None


def get_cache() -> TroubleshootingCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = TroubleshootingCache()
    return _cache_instance


if __name__ == "__main__":
    # Test cache
    print("Testing TroubleshootingCache")
    print("=" * 70)

    cache = TroubleshootingCache()

    # Test embedding cache
    test_query = "披锋问题怎么解决"
    test_embedding = [0.1] * 1024  # Fake embedding

    print(f"Setting embedding for: {test_query}")
    cache.set_embedding(test_query, test_embedding)

    print(f"Getting embedding...")
    result = cache.get_embedding(test_query)
    print(f"  Found: {result is not None}")

    # Test search cache
    print(f"\nSetting search results...")
    cache.set_search_results(
        query=test_query,
        mode="SEMANTIC",
        results={"total_found": 5, "results": [{"id": 1}]},
    )

    print(f"Getting search results...")
    result = cache.get_search_results(test_query, mode="SEMANTIC")
    print(f"  Found: {result is not None}")
    print(f"  Cached: {result.get('_cached') if result else False}")

    # Print stats
    print(f"\nCache stats:")
    stats = cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    cache.close()
