#!/usr/bin/env python3
"""
Troubleshooting Knowledge Base Indexer

Creates and manages dual-level Qdrant collections:
- troubleshooting_cases: Case-level search
- troubleshooting_issues: Issue-level search

Usage:
    from services.troubleshooting.indexer import TroubleshootingIndexer

    indexer = TroubleshootingIndexer()
    indexer.index_case(case_data)
"""

import os
import sys
from pathlib import Path

# Add project root to path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
import uuid
from typing import Dict, List
import logging

from services.troubleshooting.embedder import TroubleshootingEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TroubleshootingIndexer:
    """Index troubleshooting cases into Qdrant dual-level collections"""

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embeddings_url: str = os.getenv("EMBEDDINGS_URL", os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"))
    ):
        """
        Initialize indexer.

        Args:
            qdrant_host: Qdrant server host
            qdrant_port: Qdrant server port
            embeddings_url: Embeddings service URL
        """
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedder = TroubleshootingEmbedder(embeddings_url=embeddings_url)

        logger.info(f"Indexer initialized: Qdrant={qdrant_host}:{qdrant_port}")

        # Ensure collections exist
        self._ensure_collections()

    def _ensure_collections(self):
        """Create collections if they don't exist"""

        collections = {
            "troubleshooting_cases": {
                "description": "Case-level search (one vector per Excel file)",
                "vector_size": 1024,
                "distance": Distance.COSINE
            },
            "troubleshooting_issues": {
                "description": "Issue-level search (one vector per problem/solution)",
                "vector_size": 1024,
                "distance": Distance.COSINE
            }
        }

        for collection_name, config in collections.items():
            try:
                self.client.get_collection(collection_name)
                logger.info(f"✅ Collection '{collection_name}' exists")
            except Exception:
                logger.info(f"Creating collection '{collection_name}'...")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=config["vector_size"],
                        distance=config["distance"]
                    )
                )
                logger.info(f"✅ Created '{collection_name}'")

    def index_case(self, case_data: Dict, force_reindex: bool = True) -> Dict[str, int]:
        """
        Index a complete troubleshooting case (dual-level).

        Args:
            case_data: Case dictionary with metadata and issues
            force_reindex: If True, delete existing case before re-indexing (default: True)

        Returns:
            dict with indexing statistics
        """
        case_id = case_data['case_id']
        logger.info(f"📊 Indexing case {case_id}")

        # Delete existing case to prevent duplicates
        if force_reindex:
            logger.info(f"   Removing existing entries for {case_id}...")
            self.delete_case(case_id)

        # Level 1: Case-level indexing
        case_point_id = self._index_case_level(case_data)

        # Level 2: Issue-level indexing
        issue_point_ids = self._index_issue_level(case_data)

        logger.info(f"   ✅ Indexed: 1 case + {len(issue_point_ids)} issues")

        return {
            "case_points": 1,
            "issue_points": len(issue_point_ids),
            "case_point_id": case_point_id,
            "issue_point_ids": issue_point_ids
        }

    def _index_case_level(self, case_data: Dict) -> str:
        """Index at case level (one point per Excel file)"""

        # Generate case-level embedding
        logger.info(f"   Generating case-level embedding...")
        case_embedding = self.embedder.create_case_embedding(case_data)

        # Build payload with case metadata
        payload = {
            "case_id": case_data['case_id'],
            "part_number": case_data['metadata'].get('part_number'),
            "internal_number": case_data['metadata'].get('internal_number'),
            "mold_type": case_data['metadata'].get('mold_type'),
            "material": case_data['metadata'].get('material_t0'),
            "color": case_data['metadata'].get('color'),
            "total_issues": case_data['total_issues'],
            "issue_ids": [issue['issue_number'] for issue in case_data['issues']],
            "source_file": case_data['source_file'],
            # Add searchable text summary
            "text_summary": self._generate_case_summary(case_data),
            # NEW VLM-enriched fields
            "vlm_processed": case_data.get('vlm_processed', False),
            "vlm_summary": case_data.get('vlm_summary'),
            "key_insights": case_data.get('key_insights', []),
            "tags": case_data.get('tags', []),
            "vlm_confidence": case_data.get('vlm_confidence', 0.0),
            "vlm_job_id": case_data.get('vlm_job_id'),
            "topics": case_data.get('analysis', {}).get('topics', []),
            "entities": case_data.get('analysis', {}).get('entities', [])
        }

        # Create point
        point_id = str(uuid.uuid4())
        point = PointStruct(
            id=point_id,
            vector=case_embedding,
            payload=payload
        )

        # Upsert to Qdrant
        self.client.upsert(
            collection_name="troubleshooting_cases",
            points=[point]
        )

        return point_id

    def _index_issue_level(self, case_data: Dict) -> List[str]:
        """Index at issue level (one point per problem/solution pair)"""

        logger.info(f"   Generating embeddings for {len(case_data['issues'])} issues...")

        # Generate all issue embeddings in batch for efficiency
        issue_embeddings = []
        for issue in case_data['issues']:
            embedding = self.embedder.create_issue_embedding(issue)
            issue_embeddings.append(embedding)

        # Create points for all issues
        points = []
        point_ids = []

        for issue, embedding in zip(case_data['issues'], issue_embeddings):
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)

            # Build payload with issue details
            payload = {
                "issue_id": f"{case_data['case_id']}-{issue['issue_number']}",
                "case_id": case_data['case_id'],
                "part_number": case_data['metadata'].get('part_number'),
                "internal_number": case_data['metadata'].get('internal_number'),
                "issue_number": issue['issue_number'],
                "trial_version": issue.get('trial_version'),
                "category": issue.get('category'),
                "problem": issue.get('problem', ''),
                "solution": issue.get('solution', ''),
                "result_t1": issue.get('result_t1'),
                "result_t2": issue.get('result_t2'),
                "cause_classification": issue.get('cause_classification'),
                # Image metadata for search filtering
                "has_images": len(issue.get('images', [])) > 0,
                "image_count": len(issue.get('images', [])),
                "images": issue.get('images', []),
                # Aggregate defect types from VL analysis
                "defect_types": [
                    img.get('defect_type', '')
                    for img in issue.get('images', [])
                    if img.get('defect_type')
                ],
                # Combine text for hybrid search fallback
                "combined_text": f"{issue.get('problem', '')} {issue.get('solution', '')}",
                # NEW VLM-enriched fields
                "vlm_processed": case_data.get('vlm_processed', False),
                "vlm_confidence": self._get_max_vlm_confidence(issue.get('images', [])),
                "severity": self._get_max_severity(issue.get('images', [])),
                # Aggregate tags and insights from all images
                "tags": self._aggregate_image_tags(issue.get('images', [])),
                "key_insights": self._aggregate_image_insights(issue.get('images', [])),
                "suggested_actions": self._aggregate_suggested_actions(issue.get('images', []))
            }

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )
            points.append(point)

        # Batch upsert to Qdrant
        self.client.upsert(
            collection_name="troubleshooting_issues",
            points=points
        )

        return point_ids

    def _generate_case_summary(self, case_data: Dict) -> str:
        """Generate text summary for case-level search"""

        parts = [
            f"零件号 {case_data['metadata'].get('part_number', '')}",
            f"材料 {case_data['metadata'].get('material_t0', '')}",
            f"{case_data['total_issues']} 个问题"
        ]

        # Add first 3 issues as summary
        for issue in case_data['issues'][:3]:
            parts.append(issue.get('problem', ''))

        # Add VLM insights if available
        if case_data.get('key_insights'):
            parts.extend(case_data['key_insights'][:2])

        return " ".join(parts)

    def _get_max_vlm_confidence(self, images: List[Dict]) -> float:
        """Get maximum VLM confidence score from images"""
        if not images:
            return 0.0
        confidences = [img.get('vlm_confidence', 0.0) for img in images]
        return max(confidences) if confidences else 0.0

    def _get_max_severity(self, images: List[Dict]) -> str:
        """Get highest severity from images (high > medium > low)"""
        severity_order = {'high': 3, 'medium': 2, 'low': 1, '': 0}
        severities = [img.get('severity', '') for img in images]
        if not severities:
            return ''
        max_sev = max(severities, key=lambda s: severity_order.get(s.lower(), 0))
        return max_sev

    def _aggregate_image_tags(self, images: List[Dict]) -> List[str]:
        """Aggregate unique tags from all images"""
        tags = set()
        for img in images:
            for tag in img.get('tags', []):
                if tag:
                    tags.add(tag)
        return list(tags)[:10]  # Limit to 10 tags

    def _aggregate_image_insights(self, images: List[Dict]) -> List[str]:
        """Aggregate key insights from all images"""
        insights = []
        for img in images:
            for insight in img.get('key_insights', []):
                if insight and insight not in insights:
                    insights.append(insight)
                    if len(insights) >= 5:
                        return insights
        return insights

    def _aggregate_suggested_actions(self, images: List[Dict]) -> List[str]:
        """Aggregate suggested actions from all images"""
        actions = []
        for img in images:
            for action in img.get('suggested_actions', []):
                if action and action not in actions:
                    actions.append(action)
                    if len(actions) >= 5:
                        return actions
        return actions

    def delete_case(self, case_id: str):
        """
        Delete a case and all its issues from both collections.

        Args:
            case_id: Case ID to delete
        """
        logger.info(f"🗑️  Deleting case {case_id}")

        # Delete from case-level collection
        self.client.delete(
            collection_name="troubleshooting_cases",
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="case_id",
                        match=MatchValue(value=case_id)
                    )
                ]
            )
        )

        # Delete from issue-level collection
        self.client.delete(
            collection_name="troubleshooting_issues",
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="case_id",
                        match=MatchValue(value=case_id)
                    )
                ]
            )
        )

        logger.info(f"   ✅ Deleted case {case_id}")

    def get_collection_stats(self) -> Dict:
        """Get statistics about indexed data"""

        stats = {}

        for collection_name in ["troubleshooting_cases", "troubleshooting_issues"]:
            try:
                info = self.client.get_collection(collection_name)
                stats[collection_name] = {
                    "points_count": info.points_count,
                    "status": info.status.value if hasattr(info.status, 'value') else str(info.status)
                }
            except Exception as e:
                stats[collection_name] = {"error": str(e)}

        return stats


if __name__ == "__main__":
    # Test indexing with extracted case
    import json
    from pathlib import Path

    json_file = Path("data/troubleshooting/processed/TS-1947688-ED736A0501.json")

    if json_file.exists():
        print(f"Testing indexing with: {json_file}")
        print()

        with open(json_file, 'r', encoding='utf-8') as f:
            case = json.load(f)

        # Create indexer and index case
        indexer = TroubleshootingIndexer()

        print("Indexing case...")
        stats = indexer.index_case(case)

        print(f"\n✅ Indexing complete:")
        print(f"   Case points: {stats['case_points']}")
        print(f"   Issue points: {stats['issue_points']}")

        # Get collection stats
        print("\n📊 Collection Statistics:")
        coll_stats = indexer.get_collection_stats()
        for coll_name, coll_info in coll_stats.items():
            print(f"\n   {coll_name}:")
            for key, value in coll_info.items():
                print(f"     {key}: {value}")

    else:
        print(f"❌ Test file not found: {json_file}")
        print("   Run excel_extractor.py first")
