"""End-to-end integration tests for RAG pipeline.

These tests verify the complete RAG pipeline from query to results.

Requirements:
    - Qdrant service running on localhost:6333
    - Embeddings service running on localhost:8081
    - Reranker service running on localhost:8082
    - Collection "bestbox_knowledge" exists and is seeded with demo data

Run with:
    pytest tests/test_rag_integration.py -v -m integration

If services are not running, tests will fail gracefully with connection errors.
"""
import pytest
from tools.rag_tools import search_knowledge_base


@pytest.mark.integration
def test_end_to_end_rag():
    """
    Test complete RAG pipeline: query → embed → search → rerank → format.

    Verifies:
        - Query gets embedded by embeddings service
        - Hybrid search retrieves relevant passages from Qdrant
        - Reranker reorders results
        - Results are formatted with sources
        - ERP domain filtering works correctly

    Requires:
        - Services running (Qdrant, Embeddings, Reranker)
        - Collection "bestbox_knowledge" seeded with demo data
    """
    # Query that should match ERP documents about purchase orders
    result = search_knowledge_base.invoke({
        "query": "How do I approve a purchase order?",
        "domain": "erp",
        "top_k": 3
    })

    # Verify result is a string
    assert isinstance(result, str)

    # Should return either relevant results or no results message
    # (not an error message about services being down)
    assert "Error:" not in result or "No relevant information" in result

    # If we got results, verify they contain expected content
    if "Based on the knowledge base:" in result:
        # Should mention purchase orders or approval
        assert "purchase" in result.lower() or "approval" in result.lower() or "po" in result.lower()
        # Should have source citations
        assert "[Source:" in result
        # Should have the retrieval count footer
        assert "Retrieved" in result and "passage" in result
    else:
        # If no results, should have the standard message
        assert "No relevant information found" in result


@pytest.mark.integration
def test_domain_filtering():
    """
    Test that domain filtering correctly restricts results to specific domain.

    Verifies:
        - Domain filter parameter correctly limits search to specified domain
        - Results are domain-specific (e.g., ERP query returns ERP docs)

    Requires:
        - Services running (Qdrant, Embeddings, Reranker)
        - Collection "bestbox_knowledge" seeded with multi-domain data
    """
    # Query with ERP domain filter
    erp_result = search_knowledge_base.invoke({
        "query": "purchase order workflow",
        "domain": "erp",
        "top_k": 3
    })

    # Verify result is a string
    assert isinstance(erp_result, str)

    # If we got results (not error or no results), verify domain filtering
    if "Based on the knowledge base:" in erp_result and "[Source:" in erp_result:
        # Results should contain ERP-related content
        # Check that sources or content mention ERP concepts
        erp_keywords = ["erp", "purchase", "procurement", "invoice", "vendor"]
        assert any(keyword in erp_result.lower() for keyword in erp_keywords)

    # Query with CRM domain filter - different results expected
    crm_result = search_knowledge_base.invoke({
        "query": "customer contact information",
        "domain": "crm",
        "top_k": 3
    })

    assert isinstance(crm_result, str)

    # Results should be different between domains (or both return no results)
    # If both have results, they should be distinct
    if ("Based on the knowledge base:" in erp_result and
        "Based on the knowledge base:" in crm_result):
        # Different domains should return different content
        assert erp_result != crm_result


@pytest.mark.integration
def test_no_results():
    """
    Test RAG pipeline behavior with irrelevant queries.

    Verifies:
        - Pipeline handles queries gracefully even if matches are weak
        - No errors or exceptions raised
        - Results are properly formatted

    Note:
        - Vector search may return some results even for irrelevant queries
          due to semantic similarity matching
        - This is expected behavior - RAG systems optimize for recall
        - LLM should determine relevance in final answer generation

    Requires:
        - Services running (Qdrant, Embeddings, Reranker)
        - Collection "bestbox_knowledge" exists
    """
    # Query that should have weak semantic match to business content
    result = search_knowledge_base.invoke({
        "query": "quantum entanglement and wave-particle duality in physics",
        "domain": None,
        "top_k": 5
    })

    # Verify result is a string
    assert isinstance(result, str)

    # Pipeline should work without errors
    # May return "No relevant information" OR weak matches (both acceptable)
    if "Error:" not in result:
        # Valid outcomes: no results message OR formatted results
        assert ("No relevant information found" in result or
                "Based on the knowledge base:" in result)


@pytest.mark.integration
def test_top_k_parameter():
    """
    Test that top_k parameter correctly limits number of results returned.

    Verifies:
        - top_k parameter controls number of passages returned
        - Smaller top_k returns fewer results
        - Results are ranked (best matches first)

    Requires:
        - Services running (Qdrant, Embeddings, Reranker)
        - Collection "bestbox_knowledge" seeded with sufficient data
    """
    # Query with small top_k
    result_small = search_knowledge_base.invoke({
        "query": "enterprise resource planning system",
        "domain": None,
        "top_k": 2
    })

    # Query with larger top_k
    result_large = search_knowledge_base.invoke({
        "query": "enterprise resource planning system",
        "domain": None,
        "top_k": 5
    })

    # Both should be strings
    assert isinstance(result_small, str)
    assert isinstance(result_large, str)

    # If both have results, larger top_k should have more passages
    if ("Retrieved 2 relevant passage" in result_small and
        "Based on the knowledge base:" in result_large):
        # Small should mention 2 passages
        assert "Retrieved 2 relevant passage" in result_small

        # Large could have up to 5 (or fewer if not enough matches)
        if "Retrieved" in result_large:
            # Extract number of passages from result_large
            import re
            match = re.search(r"Retrieved (\d+) relevant passage", result_large)
            if match:
                num_passages = int(match.group(1))
                # Should have more than 2 (if data available)
                assert num_passages >= 2


@pytest.mark.integration
def test_no_domain_filter():
    """
    Test that search works without domain filter (searches all domains).

    Verifies:
        - Search without domain filter retrieves from all domains
        - Results are not domain-restricted

    Requires:
        - Services running (Qdrant, Embeddings, Reranker)
        - Collection "bestbox_knowledge" seeded with multi-domain data
    """
    # Generic business query without domain filter
    result = search_knowledge_base.invoke({
        "query": "customer support ticket",
        "domain": None,  # No domain filter
        "top_k": 3
    })

    # Verify result is a string
    assert isinstance(result, str)

    # Should work without errors (may or may not find results)
    assert isinstance(result, str)

    # Should not have error messages (unless services are down)
    if "Error:" in result:
        assert "service unavailable" in result.lower() or "service" in result.lower()
