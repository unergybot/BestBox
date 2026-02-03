#!/usr/bin/env python3
"""
Validation Pipeline

Orchestrates page rendering, VLM validation, correction, and review queue creation.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .correction_engine import CorrectionEngine
from .page_renderer import PageRenderer
from .review_queue import ReviewQueue
from .vlm_validator import VLMMappingValidator

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """End-to-end mapping validation pipeline."""

    def __init__(
        self,
        output_dir: Path,
        auto_correct_threshold: Optional[float] = None,
        skip_review_queue: bool = False
    ) -> None:
        self.output_dir = Path(output_dir)
        self.auto_correct_threshold = auto_correct_threshold or float(
            os.getenv("VLM_AUTO_CORRECT_THRESHOLD", "0.90")
        )
        self.skip_review_queue = skip_review_queue

    async def validate_case(self, excel_path: Path, case_data: Dict) -> Dict:
        """
        Validate image mappings for a case.

        Args:
            excel_path: Excel file path
            case_data: Extracted case data

        Returns:
            Updated case data with validation summary
        """
        logger.info("--- Step 2: VLM Mapping Validation ---")

        validator = VLMMappingValidator()
        if not validator.enabled:
            logger.info("VLM validation disabled; skipping validation step")
            return case_data

        try:
            render_dir = self.output_dir / "validation" / case_data["case_id"]
            renderer = PageRenderer(output_dir=render_dir)
            render_result = renderer.render(excel_path, case_data)

            page_image_map = {
                index + 1: path for index, path in enumerate(render_result.page_images)
            }
            total_pages = len(render_result.page_images)

            validations: List[Dict] = []

            max_pages = int(os.getenv("VLM_VALIDATION_MAX_PAGES", "0"))
            page_items = list(render_result.page_context.items())
            if max_pages > 0:
                page_items = page_items[:max_pages]

            for page_key, context in page_items:
                page_number = int(page_key.split("_")[-1])
                page_image = page_image_map.get(page_number)
                if not page_image:
                    continue

                rows = self._build_rows_payload(case_data, context.get("rows", []))
                images = self._build_images_payload(case_data, context.get("images", []))

                result = await validator.validate_page(
                    case_id=case_data["case_id"],
                    page_number=page_number,
                    total_pages=total_pages,
                    page_image=page_image,
                    rows=rows,
                    images=images
                )

                for validation in result.validations:
                    validation.setdefault("page_number", page_number)
                validations.extend(result.validations)

            correction_engine = CorrectionEngine(auto_correct_threshold=self.auto_correct_threshold)
            correction_result = correction_engine.apply_corrections(case_data, validations)

            if correction_result["pending_review"] > 0 and not self.skip_review_queue:
                review_queue = ReviewQueue(self.output_dir / "review_queue")
                review_queue.save_case_reviews(
                    case_data["case_id"],
                    correction_result["corrections"]
                )

            self._update_case_summary(case_data, validations, correction_result)

            return case_data

        except Exception as exc:
            logger.warning(f"VLM validation failed: {exc}")
            case_data.setdefault("vlm_validation", {})
            case_data["vlm_validation"].update(
                {
                    "status": "failed",
                    "validated_at": None
                }
            )
            return case_data

    def _build_rows_payload(self, case_data: Dict, row_ids: List[str]) -> List[Dict]:
        rows = []
        issue_map = {issue.get("row_id"): issue for issue in case_data.get("issues", [])}
        for row_id in row_ids:
            issue = issue_map.get(row_id)
            if not issue:
                continue
            rows.append(
                {
                    "row_id": row_id,
                    "values": {
                        "no": str(issue.get("issue_number")),
                        "type": issue.get("trial_version"),
                        "item": issue.get("category"),
                        "problem": issue.get("problem"),
                        "solution": issue.get("solution")
                    }
                }
            )
        return rows

    def _build_images_payload(self, case_data: Dict, image_ids: List[str]) -> List[Dict]:
        images_payload = []
        for issue in case_data.get("issues", []):
            for image in issue.get("images", []):
                if image.get("image_id") in image_ids:
                    anchor = image.get("anchor", {})
                    file_path = image.get("file_path")
                    images_payload.append(
                        {
                            "image_id": image.get("image_id"),
                            "filename": Path(file_path).name if file_path else None,
                            "file_path": file_path,
                            "anchor": {
                                "row": anchor.get("row"),
                                "col": anchor.get("col")
                            },
                            "current_mapping": {
                                "row_id": issue.get("row_id"),
                                "problem": issue.get("problem")
                            }
                        }
                    )
        return images_payload

    def _update_case_summary(self, case_data: Dict, validations: List[Dict], correction_result: Dict) -> None:
        confidences = [float(v.get("confidence", 0.0)) for v in validations if v.get("confidence") is not None]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        case_data["vlm_validation"] = {
            "status": "completed",
            "validated_at": datetime.utcnow().isoformat() + "Z",
            "pages_processed": len({v.get("page_number") for v in validations if v.get("page_number")}),
            "total_images": sum(len(issue.get("images", [])) for issue in case_data.get("issues", [])),
            "auto_corrected": correction_result.get("auto_corrected", 0),
            "pending_review": correction_result.get("pending_review", 0),
            "average_confidence": average_confidence
        }


async def extract_and_validate(
    excel_path: Path,
    output_dir: Path,
    validate_mappings: bool = True,
    auto_correct_threshold: float = 0.90,
    skip_review_queue: bool = False
) -> Dict:
    """Extract case and optionally run VLM mapping validation."""
    from .excel_extractor import ExcelTroubleshootingExtractor

    extractor = ExcelTroubleshootingExtractor(output_dir=output_dir)
    case_data = extractor.extract_case(excel_path)

    if not validate_mappings:
        return case_data

    pipeline = ValidationPipeline(
        output_dir=output_dir,
        auto_correct_threshold=auto_correct_threshold,
        skip_review_queue=skip_review_queue
    )
    return await pipeline.validate_case(excel_path, case_data)
