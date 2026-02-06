from pathlib import Path
from typing import Dict, Any, List, Optional
import os
import logging
import uuid
import time
from qdrant_client import QdrantClient, models as qmodels
from services.embeddings.client import EmbeddingService

logger = logging.getLogger(__name__)

class DocumentIndexer:
    """Index documents into Qdrant for RAG retrieval."""
    
    def __init__(
        self, 
        collection_name: str = "mold_reference_kb", 
        qdrant_host: str = "localhost", 
        qdrant_port: int = 6333, 
        embeddings_url: str = None
    ):
        self.collection = collection_name
        self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embeddings = EmbeddingService()
        
        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        try:
            self.qdrant.get_collection(self.collection)
        except Exception:
            logger.info(f"Creating collection: {self.collection}")
            self.qdrant.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=1024,  # BGE-M3 embedding size
                    distance=qmodels.Distance.COSINE
                )
            )

    async def index_document(self, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Index a document into Qdrant.
        
        Args:
            text: Document text content
            metadata: Document metadata including source, title, domain
            
        Returns:
            True if indexing succeeded
        """
        try:
            # Chunk text into smaller segments
            chunks = self._chunk_text(text)
            
            if not chunks:
                logger.warning("No chunks generated from text")
                return False
            
            points = []
            for i, chunk in enumerate(chunks):
                vector = await self.embeddings.get_embedding(chunk)
                if not vector:
                    continue
                
                point_id = str(uuid.uuid4())
                payload = {
                    "source": metadata.get("source", "unknown"),
                    "chunk_index": i,
                    "text": chunk,
                    "domain": metadata.get("domain", "general"),
                    "title": metadata.get("title", "Untitled"),
                    "timestamp": int(time.time()),
                }
                
                points.append(qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                ))

            if points:
                self.qdrant.upsert(
                    collection_name=self.collection,
                    points=points
                )
                logger.info(f"Indexed {len(points)} chunks into {self.collection}")
                return True
                
            return False

        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            return False

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Simple text chunker with overlap."""
        if not text:
            return []
            
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start += (chunk_size - overlap)
        return chunks
