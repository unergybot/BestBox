#!/usr/bin/env python3
"""
Review Queue

Stores pending mapping corrections for manual review.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

from .correction_engine import MappingCorrection

logger = logging.getLogger(__name__)


class ReviewQueue:
    """Persist review items for a case."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_case_reviews(self, case_id: str, corrections: List[MappingCorrection]) -> Path:
        """Save corrections requiring review to a JSON file."""
        review_items: List[Dict] = []
        for correction in corrections:
            if correction.status != "flagged":
                continue
            review_items.append(
                {
                    "correction_id": f"{case_id}-{correction.image_id}",
                    "case_id": case_id,
                    "image_id": correction.image_id,
                    "action": "pending",
                    "original_row": correction.original_row_id,
                    "final_row": correction.validated_row_id,
                    "vlm_confidence": correction.confidence,
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "reason": correction.reason
                }
            )

        output_path = self.output_dir / f"{case_id}_review_queue.json"
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(review_items, handle, ensure_ascii=False, indent=2)

        logger.info(f"Saved review queue to {output_path}")
        return output_path
