#!/usr/bin/env python3
"""
Correction Engine

Applies VLM validation corrections to case data and flags low-confidence items.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MappingCorrection:
    image_id: str
    page_number: int
    original_row_id: str
    original_problem: str
    validated_row_id: str
    validated_problem: str
    confidence: float
    reason: str
    status: str  # auto_corrected, flagged, confirmed
    corrected_at: datetime
    reviewed_by: Optional[str] = None


class CorrectionEngine:
    """Apply corrections to the case data structure."""

    def __init__(self, auto_correct_threshold: Optional[float] = None) -> None:
        self.auto_correct_threshold = auto_correct_threshold or float(
            os.getenv("VLM_AUTO_CORRECT_THRESHOLD", "0.90")
        )

    def apply_corrections(self, case_data: Dict, validations: List[Dict]) -> Dict:
        """Apply validation corrections to case data and return summary."""
        image_lookup = {}
        row_lookup = {}

        for issue in case_data.get("issues", []):
            row_lookup[issue.get("row_id")] = issue
            for img in issue.get("images", []):
                image_lookup.setdefault(img.get("image_id"), []).append((issue, img))

        corrections: List[MappingCorrection] = []
        auto_corrected = 0
        pending_review = 0

        for validation in validations:
            image_id = validation.get("image_id")
            if not image_id or image_id not in image_lookup:
                continue

            instances = image_lookup[image_id]
            current_mapping = validation.get("current_mapping")
            current_issue, image = self._select_instance(instances, current_mapping)
            original_row_id = current_issue.get("row_id")
            validated_row_id = validation.get("validated_mapping")
            status = validation.get("status", "confirmed")
            confidence = float(validation.get("confidence", 0.0))
            reason = validation.get("reason", "")
            page_number = int(validation.get("page_number", 0))

            if status == "confirmed" or validated_row_id == original_row_id:
                target_issue = row_lookup.get(original_row_id, current_issue)
                image = self._dedupe_image_instances(instances, target_issue)
                self._mark_validated(image, method="vlm_confirmed", confidence=confidence, reason=reason)
                corrections.append(
                    MappingCorrection(
                        image_id=image_id,
                        page_number=page_number,
                        original_row_id=original_row_id,
                        original_problem=current_issue.get("problem", ""),
                        validated_row_id=original_row_id,
                        validated_problem=current_issue.get("problem", ""),
                        confidence=confidence,
                        reason=reason,
                        status="confirmed",
                        corrected_at=datetime.utcnow()
                    )
                )
                continue

            target_issue = row_lookup.get(validated_row_id)
            if not target_issue:
                self._mark_review_required(image, confidence=confidence, reason=reason)
                pending_review += 1
                corrections.append(
                    MappingCorrection(
                        image_id=image_id,
                        page_number=page_number,
                        original_row_id=original_row_id,
                        original_problem=current_issue.get("problem", ""),
                        validated_row_id=validated_row_id or "",
                        validated_problem="",
                        confidence=confidence,
                        reason=reason,
                        status="flagged",
                        corrected_at=datetime.utcnow()
                    )
                )
                continue

            confidence_ratio = confidence / 100 if confidence > 1 else confidence
            if confidence_ratio >= self.auto_correct_threshold:
                image = self._dedupe_image_instances(instances, target_issue)
                self._mark_validated(image, method="vlm_corrected", confidence=confidence, reason=reason)
                auto_corrected += 1
                corrections.append(
                    MappingCorrection(
                        image_id=image_id,
                        page_number=page_number,
                        original_row_id=original_row_id,
                        original_problem=current_issue.get("problem", ""),
                        validated_row_id=validated_row_id,
                        validated_problem=target_issue.get("problem", ""),
                        confidence=confidence,
                        reason=reason,
                        status="auto_corrected",
                        corrected_at=datetime.utcnow()
                    )
                )
            else:
                image = self._dedupe_image_instances(instances, current_issue)
                self._mark_review_required(image, confidence=confidence, reason=reason)
                pending_review += 1
                corrections.append(
                    MappingCorrection(
                        image_id=image_id,
                        page_number=page_number,
                        original_row_id=original_row_id,
                        original_problem=current_issue.get("problem", ""),
                        validated_row_id=validated_row_id,
                        validated_problem=target_issue.get("problem", ""),
                        confidence=confidence,
                        reason=reason,
                        status="flagged",
                        corrected_at=datetime.utcnow()
                    )
                )

        self._update_issue_status(case_data)

        return {
            "corrections": corrections,
            "auto_corrected": auto_corrected,
            "pending_review": pending_review
        }

    def _dedupe_image_instances(self, instances: List, target_issue: Dict) -> Dict:
        """Remove duplicate instances and keep a single image in the target issue."""
        base_issue, base_image = instances[0]
        for issue, image in instances:
            if image in issue.get("images", []):
                issue["images"].remove(image)
        target_issue.setdefault("images", []).append(base_image)
        return base_image

    def _select_instance(self, instances: List, current_mapping: Optional[str]) -> tuple:
        """Select best image instance based on current mapping row id."""
        if current_mapping:
            for issue, image in instances:
                if issue.get("row_id") == current_mapping:
                    return issue, image
        return instances[0]

    def _mark_validated(self, image: Dict, method: str, confidence: float, reason: str) -> None:
        """Mark image mapping as validated."""
        image.setdefault("mapping_validation", {})
        image["mapping_validation"].update(
            {
                "status": "validated",
                "method": method,
                "confidence": confidence,
                "vlm_reason": reason,
                "validated_at": datetime.utcnow().isoformat() + "Z"
            }
        )

    def _mark_review_required(self, image: Dict, confidence: float, reason: str) -> None:
        """Mark image mapping as review required."""
        image.setdefault("mapping_validation", {})
        image["mapping_validation"].update(
            {
                "status": "review_required",
                "method": "vlm_corrected",
                "confidence": confidence,
                "vlm_reason": reason,
                "validated_at": datetime.utcnow().isoformat() + "Z"
            }
        )

    def _update_issue_status(self, case_data: Dict) -> None:
        """Update issue-level mapping status counts."""
        for issue in case_data.get("issues", []):
            images = issue.get("images", [])
            validated = sum(
                1 for img in images if img.get("mapping_validation", {}).get("status") == "validated"
            )
            pending_review = sum(
                1 for img in images if img.get("mapping_validation", {}).get("status") == "review_required"
            )
            issue["image_mapping_status"] = {
                "total": len(images),
                "validated": validated,
                "pending_review": pending_review
            }
