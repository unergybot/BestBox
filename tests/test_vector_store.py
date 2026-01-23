"""Tests for VectorStore Qdrant client."""

import pytest
from services.rag_pipeline.vector_store import VectorStore


def test_vector_store_create_collection():
    """Test creating Qdrant collection"""
    store = VectorStore(url="http://localhost:6333")
    collection_name = "test_collection"

    store.create_collection(
        collection_name=collection_name,
        vector_size=1024,
        enable_bm25=True
    )

    assert store.collection_exists(collection_name)

    # Cleanup
    store.delete_collection(collection_name)


def test_vector_store_upsert_documents():
    """Test upserting documents with embeddings"""
    store = VectorStore(url="http://localhost:6333")
    collection_name = "test_upsert_collection"

    # Create collection
    store.create_collection(
        collection_name=collection_name,
        vector_size=1024,
        enable_bm25=True
    )

    # Prepare test documents
    documents = [
        {
            "id": 1,  # Use integer ID
            "vector": [0.1] * 1024,  # Mock BGE-M3 embedding
            "payload": {
                "text": "This is a test document about enterprise resource planning.",
                "source": "test_erp.pdf",
                "chunk_id": 0,
            },
            "sparse_vector": {
                "indices": [10, 25, 42],
                "values": [0.5, 0.3, 0.2],
            },
        },
        {
            "id": 2,  # Use integer ID
            "vector": [0.2] * 1024,
            "payload": {
                "text": "Customer relationship management systems help businesses.",
                "source": "test_crm.pdf",
                "chunk_id": 1,
            },
            "sparse_vector": {
                "indices": [15, 30, 50],
                "values": [0.6, 0.4, 0.1],
            },
        },
    ]

    # Upsert documents
    store.upsert_documents(collection_name, documents)

    # Verify documents were inserted by checking collection info
    collection_info = store.client.get_collection(collection_name)
    assert collection_info.points_count == 2

    # Cleanup
    store.delete_collection(collection_name)
