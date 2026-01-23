"""Integration tests for RAG tools."""
import pytest
from tools.rag_tools import search_knowledge_base

# Note: This is an integration test that requires:
# - Qdrant running (docker-compose up -d)
# - Embeddings service running (scripts/start-embeddings.sh)
# - Reranker service running (scripts/start-reranker.sh)
# - Test data seeded

@pytest.mark.integration
def test_search_knowledge_base():
    """Test RAG tool returns formatted results"""
    query = "How do I approve a purchase order?"

    # LangChain @tool decorator wraps function - use .invoke()
    result = search_knowledge_base.invoke({"query": query, "domain": "erp", "top_k": 3})

    # Should return string with sources
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Source:" in result or "No relevant information" in result


@pytest.mark.integration
def test_search_knowledge_base_no_domain():
    """Test search without domain filter"""
    query = "system architecture"

    result = search_knowledge_base.invoke({"query": query, "top_k": 2})

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.integration
def test_search_knowledge_base_no_results():
    """Test handling of no results"""
    query = "xyzabc123nonexistentquerystringforsurethatwontmatch"

    result = search_knowledge_base.invoke({"query": query, "top_k": 5})

    assert isinstance(result, str)
    assert "No relevant information" in result
