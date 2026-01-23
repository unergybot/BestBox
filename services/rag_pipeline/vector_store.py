"""Qdrant vector store client for BestBox RAG pipeline."""

import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    SparseVectorParams,
    SparseIndexParams,
)

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Wrapper for Qdrant vector database client.

    Handles collection management and document operations for the RAG pipeline.
    Supports both dense vectors (BGE-M3 embeddings) and optional BM25 sparse vectors.
    """

    def __init__(self, url: str = "http://localhost:6333"):
        """
        Initialize Qdrant client.

        Args:
            url: Qdrant server URL (default: http://localhost:6333)
        """
        self.client = QdrantClient(url=url)
        logger.info(f"Initialized Qdrant client connected to {url}")

    def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.

        Args:
            collection_name: Name of the collection to check

        Returns:
            True if collection exists, False otherwise
        """
        try:
            collections = self.client.get_collections()
            return any(col.name == collection_name for col in collections.collections)
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False

    def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1024,
        distance: Distance = Distance.COSINE,
        enable_bm25: bool = True,
    ) -> None:
        """
        Create a new Qdrant collection with dense and optional sparse vectors.

        Args:
            collection_name: Name for the new collection
            vector_size: Dimension of dense vectors (default: 1024 for BGE-M3)
            distance: Distance metric (default: COSINE)
            enable_bm25: Whether to enable BM25 sparse vectors (default: True)
        """
        if self.collection_exists(collection_name):
            logger.warning(f"Collection '{collection_name}' already exists, skipping creation")
            return

        try:
            vectors_config = VectorParams(
                size=vector_size,
                distance=distance,
            )

            sparse_vectors_config = None
            if enable_bm25:
                sparse_vectors_config = {
                    "text": SparseVectorParams(
                        index=SparseIndexParams(
                            on_disk=False,
                        )
                    )
                }

            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config,
                sparse_vectors_config=sparse_vectors_config,
            )
            logger.info(f"Created collection '{collection_name}' with vector_size={vector_size}, bm25={enable_bm25}")
        except Exception as e:
            logger.error(f"Error creating collection '{collection_name}': {e}")
            raise

    def delete_collection(self, collection_name: str) -> None:
        """
        Delete a collection.

        Args:
            collection_name: Name of the collection to delete
        """
        try:
            if self.collection_exists(collection_name):
                self.client.delete_collection(collection_name)
                logger.info(f"Deleted collection '{collection_name}'")
            else:
                logger.warning(f"Collection '{collection_name}' does not exist, skipping deletion")
        except Exception as e:
            logger.error(f"Error deleting collection '{collection_name}': {e}")
            raise

    def upsert_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
    ) -> None:
        """
        Upsert document chunks into the collection.

        Each document should have:
        - id: Unique identifier (int or UUID)
        - vector: Dense embedding (list of floats, size must match collection config)
        - payload: Metadata dict (e.g., {"text": "...", "source": "...", "chunk_id": 0})
        - sparse_vector (optional): BM25 sparse vector with "indices" and "values" keys

        Args:
            collection_name: Target collection name
            documents: List of document dicts with id, vector, payload, and optional sparse_vector
        """
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        try:
            points = []
            for doc in documents:
                point_kwargs = {
                    "id": doc["id"],
                    "vector": doc["vector"],
                    "payload": doc.get("payload", {}),
                }

                # Add sparse vector if present
                if "sparse_vector" in doc:
                    point_kwargs["vector"] = {
                        "": doc["vector"],  # Default dense vector
                        "text": doc["sparse_vector"],  # Named sparse vector
                    }

                points.append(PointStruct(**point_kwargs))

            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(f"Upserted {len(documents)} documents to collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Error upserting documents to '{collection_name}': {e}")
            raise
