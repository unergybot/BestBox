#!/usr/bin/env python3
"""
VLM Mapping Validator

Uses the external VLM service to validate image-to-row mappings on rendered pages.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    from services.vlm import VLMServiceClient
    from services.vlm.models import VLMJobOptions, AnalysisDepth
    VLM_CLIENT_AVAILABLE = True
except ImportError:
    VLM_CLIENT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PageValidationResult:
    """Result for a single page validation."""

    page_number: int
    validations: List[Dict]
    average_confidence: float
    raw_response: Optional[str] = None


class VLMMappingValidator:
    """Validate image mappings using VLM."""

    def __init__(
        self,
        vlm_service_url: Optional[str] = None,
        enabled: Optional[bool] = None,
        language: str = "zh",
        max_retries: int = 2
    ) -> None:
        self.vlm_service_url = vlm_service_url or os.getenv("VLM_SERVICE_URL", "http://192.168.1.196:8081")
        self.enabled = enabled if enabled is not None else os.getenv("VLM_VALIDATION_ENABLED", "false").lower() == "true"
        self.language = language
        self.max_retries = max_retries
        self.prompt_template = os.getenv("VLM_VALIDATION_PROMPT_TEMPLATE", "mapping_validation")

        if self.enabled and not VLM_CLIENT_AVAILABLE:
            logger.warning("VLM client not available; mapping validation disabled")
            self.enabled = False

    async def validate_page(
        self,
        case_id: str,
        page_number: int,
        total_pages: int,
        page_image: Path,
        rows: List[Dict],
        images: List[Dict]
    ) -> PageValidationResult:
        """
        Validate mappings for a single page.

        Args:
            page_number: Page index (1-based)
            page_image: Rendered page image path
            rows: List of row dicts for this page
            images: List of image dicts for this page

        Returns:
            PageValidationResult with validation entries
        """
        if not self.enabled:
            return PageValidationResult(page_number, [], 0.0, raw_response=None)

        if not images or not rows:
            return PageValidationResult(page_number, [], 0.0, raw_response=None)

        mapping_context = self._build_mapping_context(case_id, page_number, total_pages, rows, images)
        extracted_image_paths = [Path(img["file_path"]) for img in images]

        options = VLMJobOptions(
            analysis_depth=AnalysisDepth.DETAILED,
            output_language=self.language,
            include_ocr=True,
            max_tokens=2048
        )

        result_text = None
        for attempt in range(1, self.max_retries + 2):
            try:
                client = VLMServiceClient(base_url=self.vlm_service_url)
                response = await client.validate_mappings(
                    page_image_path=page_image,
                    extracted_image_paths=extracted_image_paths,
                    mapping_context=mapping_context,
                    options={
                        "analysis_depth": "detailed",
                        "output_language": self.language,
                        "include_visual_reasoning": True,
                        "include_ocr": True,
                        "confidence_threshold": float(os.getenv("VLM_AUTO_CORRECT_THRESHOLD", "0.90")),
                        "max_tokens": 2048
                    }
                )
                job_id = response.get("job_id")
                result_payload = await client.wait_for_validation(
                    job_id=job_id,
                    timeout=int(os.getenv("VLM_TIMEOUT", 600))
                )
                await client.close()

                validations = self._extract_validations(result_payload)
                average_confidence = self._average_confidence(validations)

                return PageValidationResult(
                    page_number=page_number,
                    validations=validations,
                    average_confidence=average_confidence,
                    raw_response=json.dumps(result_payload, ensure_ascii=False)
                )
            except Exception as exc:
                logger.warning(f"VLM validation attempt {attempt} failed on page {page_number}: {exc}")
                if attempt >= self.max_retries + 1:
                    break
                await asyncio.sleep(1.0)

        return PageValidationResult(page_number, [], 0.0, raw_response=None)

    def _build_mapping_context(
        self,
        case_id: str,
        page_number: int,
        total_pages: int,
        rows: List[Dict],
        images: List[Dict]
    ) -> Dict:
        """Build mapping context payload for VLM validation API."""
        return {
            "case_id": case_id,
            "page_number": page_number,
            "total_pages": total_pages,
            "columns": [
                {"id": "no", "label": "NO", "description": "Issue number"},
                {"id": "type", "label": "型试", "description": "Trial version"},
                {"id": "item", "label": "项目", "description": "Category"},
                {"id": "problem", "label": "問題点", "description": "Problem description"},
                {"id": "solution", "label": "原因，对策", "description": "Cause and solution"}
            ],
            "rows": rows,
            "images": images
        }

    def _extract_validations(self, result_payload: Dict) -> List[Dict]:
        """Normalize validation payload to internal schema."""
        result = result_payload.get("result") or {}
        validations = result.get("validations") or []
        normalized = []
        for entry in validations:
            validation_result = entry.get("validation_result", {})
            current_mapping = entry.get("current_mapping", {})
            validated_mapping = entry.get("validated_mapping", {})
            normalized.append(
                {
                    "image_id": entry.get("image_id"),
                    "current_mapping": current_mapping.get("row_id") if isinstance(current_mapping, dict) else current_mapping,
                    "validated_mapping": validated_mapping.get("row_id") if isinstance(validated_mapping, dict) else validated_mapping,
                    "status": validation_result.get("status"),
                    "confidence": validation_result.get("confidence"),
                    "reason": validation_result.get("reasoning")
                }
            )
        return normalized

    def _average_confidence(self, validations: List[Dict]) -> float:
        if not validations:
            return 0.0
        confidences = []
        for validation in validations:
            confidence = validation.get("confidence")
            if confidence is None:
                continue
            value = float(confidence)
            confidences.append(value * 100 if value <= 1 else value)
        return sum(confidences) / len(confidences) if confidences else 0.0
