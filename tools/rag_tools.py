"""RAG tools for agent knowledge base access."""
import logging
import requests
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)

# Service URLs
EMBEDDINGS_URL = "http://localhost:8081"
RERANKER_URL = "http://localhost:8082"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "bestbox_knowledge"

# Request timeout
TIMEOUT = 5


def _embed_query(query: str) -> Optional[List[float]]:
    """
    Embed query using embeddings service.

    Args:
        query: Query text to embed

    Returns:
        Embedding vector or None if service fails
    """
    try:
        response = requests.post(
            f"{EMBEDDINGS_URL}/embed",
            json={"inputs": query, "normalize": True},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]
    except requests.exceptions.RequestException as e:
        logger.error(f"Embeddings service error: {e}")
        return None


def _hybrid_search(
    query_vector: List[float],
    domain: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search on Qdrant.

    Args:
        query_vector: Query embedding vector
        domain: Optional domain filter (erp, crm, it_ops, oa)
        limit: Number of results to retrieve

    Returns:
        List of search results with payload and score
    """
    try:
        client = QdrantClient(url=QDRANT_URL)

        # Build filter if domain specified
        query_filter = None
        if domain:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="domain",
                        match=MatchValue(value=domain)
                    )
                ]
            )

        # Perform query using query_points
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        # Convert to dict format
        search_results = []
        for point in response.points:
            search_results.append({
                "id": point.id,
                "score": point.score,
                "payload": point.payload
            })

        return search_results

    except Exception as e:
        logger.error(f"Qdrant search error: {e}")
        return []


def _rerank_results(
    query: str,
    passages: List[str],
) -> Optional[List[int]]:
    """
    Rerank passages using reranker service.

    Args:
        query: Original query text
        passages: List of passage texts to rerank

    Returns:
        Ranked indices (best first) or None if service fails
    """
    try:
        response = requests.post(
            f"{RERANKER_URL}/rerank",
            json={"query": query, "passages": passages},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data["ranked_indices"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Reranker service error: {e}")
        return None


def _format_results(results: List[Dict[str, Any]]) -> str:
    """
    Format search results with sources and citations.

    Args:
        results: List of result dicts with payload containing text, source, section

    Returns:
        Formatted string with sources
    """
    if not results:
        return "No relevant information found in the knowledge base."

    formatted_parts = ["Based on the knowledge base:\n"]

    for result in results:
        payload = result.get("payload", {})
        text = payload.get("text", "")
        source = payload.get("source", "unknown")
        section = payload.get("section", "")

        # Build source citation
        if section:
            citation = f"[Source: {source}, {section}]"
        else:
            citation = f"[Source: {source}]"

        # Add to formatted output
        formatted_parts.append(f"\n{citation}")
        formatted_parts.append(f"{text}\n")

    formatted_parts.append(f"\n---\nRetrieved {len(results)} relevant passage(s).")

    return "".join(formatted_parts)


@tool
def search_knowledge_base(
    query: str,
    domain: Optional[str] = None,
    top_k: int = 5
) -> str:
    """
    Search the knowledge base using RAG pipeline (embeddings → hybrid search → reranking).

    Use this tool to find information in BestBox documentation, procedures, and knowledge articles.
    The search returns relevant passages with source citations.

    Args:
        query: Natural language search query
        domain: Optional domain filter - "erp", "crm", "it_ops", or "oa" (default: None for all domains)
        top_k: Number of top results to return after reranking (default: 5)

    Returns:
        Formatted string with search results and sources, or error message if services unavailable

    Example:
        >>> search_knowledge_base("How do I approve a purchase order?", domain="erp", top_k=3)
        "Based on the knowledge base:

        [Source: erp_procedures.md, Purchase Orders]
        To approve a purchase order, navigate to ERP > Procurement > Pending POs...

        ---
        Retrieved 3 relevant passage(s)."
    """
    # Step 1: Embed query
    logger.info(f"Searching knowledge base: query='{query}', domain={domain}, top_k={top_k}")

    query_vector = _embed_query(query)
    if query_vector is None:
        return (
            "Error: Embeddings service unavailable. "
            "Please ensure the embeddings service is running (scripts/start-embeddings.sh)."
        )

    # Step 2: Hybrid search (get top 20 for reranking)
    search_results = _hybrid_search(query_vector, domain=domain, limit=20)

    if not search_results:
        return "No relevant information found in the knowledge base."

    # Step 3: Rerank results
    passages = [result["payload"].get("text", "") for result in search_results]
    ranked_indices = _rerank_results(query, passages)

    if ranked_indices is None:
        # Fallback: use hybrid search results without reranking
        logger.warning("Reranker service unavailable, using hybrid search results without reranking")
        top_results = search_results[:top_k]
    else:
        # Take top_k from reranked results
        top_results = [search_results[i] for i in ranked_indices[:top_k]]

    # Step 4: Format with sources
    return _format_results(top_results)
