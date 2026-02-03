#!/usr/bin/env python3
"""Clean up Qdrant troubleshooting collections and re-index with validation."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clear_troubleshooting_collections(qdrant_host: str = "localhost", qdrant_port: int = 6333):
    """Delete all points from troubleshooting collections."""
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    collections = ["troubleshooting_cases", "troubleshooting_issues"]
    
    for collection_name in collections:
        try:
            collection_info = client.get_collection(collection_name)
            points_count = collection_info.points_count
            
            if points_count > 0:
                logger.info(f"Deleting {points_count} points from '{collection_name}'...")
                
                # Delete all points using an empty filter (matches everything)
                client.delete(
                    collection_name=collection_name,
                    points_selector=Filter(must=[])
                )
                
                logger.info(f"✅ Cleared all points from '{collection_name}'")
            else:
                logger.info(f"Collection '{collection_name}' is already empty")
                
        except Exception as e:
            logger.error(f"Error clearing '{collection_name}': {e}")


def check_collection_stats(qdrant_host: str = "localhost", qdrant_port: int = 6333):
    """Check current stats of troubleshooting collections."""
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    collections = ["troubleshooting_cases", "troubleshooting_issues"]
    
    logger.info("\n" + "="*60)
    logger.info("QDRANT COLLECTIONS STATUS")
    logger.info("="*60)
    
    for collection_name in collections:
        try:
            collection_info = client.get_collection(collection_name)
            logger.info(f"\n📊 {collection_name}:")
            logger.info(f"   Points count: {collection_info.points_count}")
            logger.info(f"   Vectors: {collection_info.vectors_count}")
        except Exception as e:
            logger.error(f"❌ Error accessing '{collection_name}': {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up Qdrant troubleshooting collections")
    parser.add_argument("--host", default="localhost", help="Qdrant host")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant port")
    parser.add_argument("--check-only", action="store_true", help="Only check stats, don't delete")
    
    args = parser.parse_args()
    
    check_collection_stats(args.host, args.port)
    
    if not args.check_only:
        logger.info("\n" + "="*60)
        logger.info("CLEARING COLLECTIONS")
        logger.info("="*60)
        clear_troubleshooting_collections(args.host, args.port)
        
        logger.info("\n" + "="*60)
        logger.info("STATUS AFTER CLEAR")
        logger.info("="*60)
        check_collection_stats(args.host, args.port)
