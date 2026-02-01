#!/usr/bin/env python3
"""
Troubleshooting Embedder

Generates embeddings for troubleshooting data by combining:
- Text (problem descriptions, solutions)
- VL descriptions (image analysis results)
- Metadata (trial versions, results)

Uses existing BGE-M3 embeddings service.

Usage:
    from services/troubleshooting.embedder import TroubleshootingEmbedder

    embedder = TroubleshootingEmbedder()
    case_embedding = embedder.create_case_embedding(case_data)
    issue_embedding = embedder.create_issue_embedding(issue_data)
"""

import os
import requests
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TroubleshootingEmbedder:
    """Generate embeddings for troubleshooting data"""

    def __init__(self, embeddings_url: str = ""):
        """
        Initialize embedder.

        Args:
            embeddings_url: URL of BGE-M3 embeddings service
        """
        if not embeddings_url:
            embeddings_url = os.getenv("EMBEDDINGS_URL", os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8081"))
        if embeddings_url.endswith("/v1"):
            embeddings_url = embeddings_url[:-3]

        self.embeddings_url = embeddings_url

        # Check service health
        try:
            response = requests.get(f"{embeddings_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ Embeddings service connected: {embeddings_url}")
            else:
                logger.warning(f"⚠️  Embeddings service returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️  Embeddings service not available at {embeddings_url}")

    def create_case_embedding(self, case_data: Dict) -> List[float]:
        """
        Create case-level embedding (summary of all issues).

        Args:
            case_data: Complete case dictionary

        Returns:
            1024-dim embedding vector
        """
        # Aggregate issue texts
        issue_texts = []
        for issue in case_data['issues'][:5]:  # Top 5 issues for summary
            text = f"{issue['problem']} {issue['solution']}"
            issue_texts.append(text)

        # Build case summary text
        summary_parts = [
            f"案件编号: {case_data['case_id']}",
            f"零件号: {case_data['metadata'].get('part_number', '')}",
            f"材料: {case_data['metadata'].get('material_t0', '')}",
            f"问题总数: {case_data['total_issues']}",
            f"主要问题: {' '.join(issue_texts)}"
        ]

        summary_text = " ".join(summary_parts)

        return self._get_embedding(summary_text)

    def create_issue_embedding(self, issue_data: Dict) -> List[float]:
        """
        Create issue-level embedding (problem + solution + VL descriptions + VLM metadata).

        This combines textual and visual information into a single semantic vector.

        Args:
            issue_data: Issue dictionary

        Returns:
            1024-dim embedding vector
        """
        parts = []

        # Core problem and solution
        if issue_data.get('problem'):
            parts.append(f"问题: {issue_data['problem']}")

        if issue_data.get('solution'):
            parts.append(f"解决方案: {issue_data['solution']}")

        # Add VL-enriched image descriptions
        for img in issue_data.get('images', []):
            if img.get('vl_description'):
                parts.append(f"图像显示: {img['vl_description']}")

            if img.get('defect_type'):
                parts.append(f"缺陷类型: {img['defect_type']}")

            if img.get('text_in_image'):
                parts.append(f"图像文字: {img['text_in_image']}")

            # NEW: Add VLM-enriched fields from images
            if img.get('severity'):
                parts.append(f"严重程度: {img['severity']}")

            if img.get('key_insights'):
                for insight in img['key_insights'][:3]:  # Limit to top 3
                    parts.append(f"洞察: {insight}")

            if img.get('suggested_actions'):
                for action in img['suggested_actions'][:3]:
                    parts.append(f"建议措施: {action}")

        # Add structured metadata as searchable text
        if issue_data.get('trial_version'):
            parts.append(f"试模阶段: {issue_data['trial_version']}")

        if issue_data.get('result_t1'):
            parts.append(f"T1结果: {issue_data['result_t1']}")

        if issue_data.get('result_t2'):
            parts.append(f"T2结果: {issue_data['result_t2']}")

        if issue_data.get('category'):
            parts.append(f"类别: {issue_data['category']}")

        # NEW: Add VLM-enriched case-level fields (if propagated to issue)
        if issue_data.get('key_insights'):
            parts.append(f"关键洞察: {' '.join(issue_data['key_insights'][:5])}")

        if issue_data.get('analysis', {}).get('topics'):
            parts.append(f"主题: {' '.join(issue_data['analysis']['topics'][:5])}")

        if issue_data.get('tags'):
            parts.append(f"标签: {' '.join(issue_data['tags'][:5])}")

        # Combine all parts
        combined_text = " ".join(parts)

        return self._get_embedding(combined_text)

    def create_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of 1024-dim embedding vectors
        """
        if not texts:
            return []

        return self._get_embeddings_batch(texts)

    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for single text via BGE-M3 service.

        Args:
            text: Text to embed

        Returns:
            1024-dim embedding vector
        """
        response = requests.post(
            f"{self.embeddings_url}/embed",
            json={"inputs": [text], "normalize": True},
            timeout=30
        )

        response.raise_for_status()
        return response.json()["embeddings"][0]

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of 1024-dim embedding vectors
        """
        response = requests.post(
            f"{self.embeddings_url}/embed",
            json={"inputs": texts, "normalize": True},
            timeout=60  # Longer timeout for batch
        )

        response.raise_for_status()
        return response.json()["embeddings"]


if __name__ == "__main__":
    # Test embeddings generation
    import json
    from pathlib import Path

    json_file = Path("data/troubleshooting/processed/TS-1947688-ED736A0501.json")

    if json_file.exists():
        print(f"Testing embeddings with: {json_file}")

        with open(json_file, 'r', encoding='utf-8') as f:
            case = json.load(f)

        embedder = TroubleshootingEmbedder()

        # Test case-level embedding
        print("\n1. Generating case-level embedding...")
        case_emb = embedder.create_case_embedding(case)
        print(f"   ✅ Case embedding: {len(case_emb)}-dim vector")
        print(f"   Sample values: [{case_emb[0]:.4f}, {case_emb[1]:.4f}, ...]")

        # Test issue-level embedding
        print("\n2. Generating issue-level embedding...")
        issue = case['issues'][0]
        issue_emb = embedder.create_issue_embedding(issue)
        print(f"   ✅ Issue embedding: {len(issue_emb)}-dim vector")
        print(f"   Sample values: [{issue_emb[0]:.4f}, {issue_emb[1]:.4f}, ...]")

        print("\n✅ Embeddings test complete")
    else:
        print(f"❌ Test file not found: {json_file}")
        print("   Run excel_extractor.py first to create test data")
