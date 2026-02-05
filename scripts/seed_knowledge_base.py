#!/usr/bin/env python3
"""
Knowledge Base Seeding Script

Ingests demo documents from data/demo_docs/ into Qdrant vector store.
Processes documents through the full RAG pipeline:
  1. Ingest document (extract text + metadata)
  2. Chunk text (512 tokens, 100 overlap)
  3. Generate embeddings (BGE-M3 via embeddings service)
  4. Store in Qdrant with BM25 hybrid search enabled

Usage:
    python scripts/seed_knowledge_base.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
import uuid
import re
import hashlib
from qdrant_client.models import Distance, PointStruct, SparseVector
from typing import List, Dict, Any
from services.rag_pipeline.ingest import DocumentIngester
from services.rag_pipeline.chunker import TextChunker
from services.rag_pipeline.vector_store import VectorStore


def get_embeddings(texts: List[str], timeout: int = 30) -> List[List[float]]:
    """
    Generate embeddings via embeddings service.

    Args:
        texts: List of text strings to embed
        timeout: Request timeout in seconds

    Returns:
        List of embedding vectors
    """
    response = requests.post(
        "http://localhost:8081/embed",
        json={"inputs": texts, "normalize": True},
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()["embeddings"]


def build_sparse_vector(text: str, size: int = 65536) -> SparseVector:
    """Build a simple hashed sparse vector for BM25-style hybrid search."""
    term_counts: Dict[int, int] = {}
    for token in re.findall(r"[A-Za-z0-9_]+", text.lower()):
        token_hash = hashlib.md5(token.encode("utf-8")).hexdigest()
        idx = int(token_hash[:8], 16) % size
        term_counts[idx] = term_counts.get(idx, 0) + 1

    indices = list(term_counts.keys())
    values = [float(term_counts[i]) for i in indices]
    return SparseVector(indices=indices, values=values)


def seed_knowledge_base():
    """Main seeding function."""
    print("🚀 Starting knowledge base seeding...")
    print()

    # Initialize components
    print("Initializing RAG pipeline components...")
    ingester = DocumentIngester()
    chunker = TextChunker(chunk_size=512, overlap_percentage=0.195)  # ~100 tokens overlap
    vector_store = VectorStore()

    # Create collection if not exists
    collection_name = "bestbox_knowledge"
    print(f"Setting up Qdrant collection: {collection_name}")

    try:
        vector_store.client.get_collection(collection_name)
        print(f"✅ Collection '{collection_name}' already exists")
    except Exception:
        print(f"Creating new collection: {collection_name}")
        vector_store.create_collection(
            collection_name=collection_name,
            vector_size=1024,
            distance=Distance.COSINE,
            enable_bm25=True,
        )
        print("✅ Collection created with 1024-dim vectors and BM25 sparse vectors")

    print()

    # Process each domain
    demo_docs_dir = project_root / "data" / "demo_docs"
    domains = ["erp", "crm", "itops", "oa", "hudson"]

    total_docs = 0
    total_chunks = 0
    total_vectors = 0

    for domain in domains:
        domain_dir = demo_docs_dir / domain

        if not domain_dir.exists():
            print(f"⚠️  Domain directory not found: {domain_dir}")
            continue

        print(f"📁 Processing domain: {domain.upper()}")

        # Find all markdown, PDF, and DOCX files
        doc_files = []
        for ext in ["*.md", "*.pdf", "*.docx"]:
            doc_files.extend(domain_dir.glob(ext))

        if not doc_files:
            print(f"  No documents found in {domain_dir}")
            continue

        for doc_path in doc_files:
            print(f"  📄 Ingesting: {doc_path.name}")

            try:
                # Step 1: Ingest document
                doc = ingester.ingest_document(
                    doc_path=doc_path,
                    domain=domain
                )

                if doc is None:
                    print(f"     ❌ Failed to ingest document")
                    continue

                total_docs += 1

                # Step 2: Chunk text
                chunks = chunker.chunk_text(text=doc["text"])
                print(f"     Created {len(chunks)} chunks")
                total_chunks += len(chunks)

                # Step 3: Generate embeddings
                chunk_texts = [chunk["text"] for chunk in chunks]
                print(f"     Generating embeddings...")
                embeddings = get_embeddings(chunk_texts, timeout=30)

                # Step 4: Prepare Qdrant documents
                points = []
                doc_stem = doc_path.stem

                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_id = f"{doc_stem}_chunk{i}"

                    sparse_vector = build_sparse_vector(chunk["text"])
                    point = PointStruct(
                        id=str(uuid.uuid4()),  # Use UUID for Qdrant
                        vector={
                            "": embedding,
                            "text": sparse_vector,
                        },
                        payload={
                            "chunk_id": chunk_id,
                            "text": chunk["text"],
                            "domain": domain,
                            "source": doc["metadata"]["source"],
                            "file_path": str(doc_path),
                            "title": doc["metadata"].get("title", doc_path.stem),
                            "section": chunk.get("section", ""),
                            "token_count": chunk["token_count"],
                            "start_char": chunk["start_char"],
                            "end_char": chunk["end_char"],
                        },
                    )
                    points.append(point)

                # Step 5: Upsert to Qdrant
                vector_store.client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"     💾 Stored {len(points)} vectors in Qdrant")
                total_vectors += len(points)

            except Exception as e:
                print(f"     ❌ Error processing {doc_path.name}: {str(e)}")
                continue

        print()

    # Print summary
    print("=" * 60)
    print("✅ Knowledge base seeding complete!")
    print()
    print(f"📊 Summary:")
    print(f"  Documents processed: {total_docs}")
    print(f"  Chunks created: {total_chunks}")
    print(f"  Vectors stored: {total_vectors}")
    print(f"  Collection: {collection_name}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        seed_knowledge_base()
    except KeyboardInterrupt:
        print("\n\n⚠️  Seeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Seeding failed: {str(e)}")
        sys.exit(1)
