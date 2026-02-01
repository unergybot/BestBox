#!/usr/bin/env python3
"""
VL Processor for Troubleshooting Images

Enriches extracted images with Vision-Language model descriptions.
Supports both the legacy local VL service and the new external VLM service.

Usage:
    from services.troubleshooting.vl_processor import VLProcessor

    processor = VLProcessor()
    enriched_case = processor.enrich_case(case_data)

    # Or async with external VLM service:
    enriched_case = await processor.enrich_case_async(case_data)
"""

import os
import asyncio
import requests
from pathlib import Path
from typing import Dict, List, Optional
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try importing VLM service client
try:
    from services.vlm import VLMServiceClient, VLMResult
    from services.vlm.models import VLMJobOptions, AnalysisDepth
    VLM_CLIENT_AVAILABLE = True
except ImportError:
    VLM_CLIENT_AVAILABLE = False
    logger.info("VLM service client not available, using legacy mode only")


class VLProcessor:
    """Process images with VLM and enrich issue data"""

    def __init__(
        self,
        vl_service_url: str = "http://localhost:8083",
        vlm_service_url: Optional[str] = None,
        max_workers: int = 4,
        language: str = "zh",
        enabled: bool = False,
        use_vlm_service: bool = True  # Prefer external VLM service when available
    ):
        """
        Initialize VL processor.

        Args:
            vl_service_url: URL of legacy local VL service
            vlm_service_url: URL of external VLM service (192.168.1.196:8081)
            max_workers: Max concurrent requests
            language: Output language ('zh' or 'en')
            enabled: Enable VL processing (disabled by default)
            use_vlm_service: Use external VLM service instead of local
        """
        self.vl_service_url = vl_service_url
        self.vlm_service_url = vlm_service_url or os.getenv("VLM_SERVICE_URL", "http://192.168.1.196:8081")
        self.max_workers = max_workers
        self.language = language
        self.enabled = enabled or os.getenv("VLM_ENABLED", "false").lower() == "true"
        self.use_vlm_service = use_vlm_service and VLM_CLIENT_AVAILABLE
        self.service_available = False

        if not self.enabled:
            logger.info("VL processing DISABLED (text-only search mode)")
            logger.info("   Images will be extracted and stored, but not analyzed")
            return

        # Check service availability
        if self.use_vlm_service:
            self._check_vlm_service()
        else:
            self._check_legacy_service()

    def _check_vlm_service(self):
        """Check external VLM service health"""
        try:
            response = requests.get(f"{self.vlm_service_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"VLM service connected: {self.vlm_service_url}")
                self.service_available = True
            else:
                logger.warning(f"VLM service returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"VLM service not available at {self.vlm_service_url}")
            logger.warning("   Falling back to legacy VL service")
            self.use_vlm_service = False
            self._check_legacy_service()

    def _check_legacy_service(self):
        """Check legacy local VL service health"""
        try:
            response = requests.get(f"{self.vl_service_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"Legacy VL service connected: {self.vl_service_url}")
                self.service_available = True
            else:
                logger.warning(f"Legacy VL service returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Legacy VL service not available at {self.vl_service_url}")
            logger.warning("   Images will be processed when service becomes available")

    def enrich_case(self, case_data: Dict) -> Dict:
        """
        Add VL descriptions to all images in a case (synchronous version).
        Uses asyncio.run() internally if VLM service is enabled.

        Args:
            case_data: Case dictionary from ExcelExtractor

        Returns:
            Enriched case data with VL descriptions
        """
        if self.use_vlm_service and self.enabled:
            # Use async VLM service
            return asyncio.run(self.enrich_case_async(case_data))
        else:
            # Use legacy synchronous processing
            return self._enrich_case_legacy(case_data)

    async def enrich_case_async(self, case_data: Dict) -> Dict:
        """
        Add VL descriptions to all images using async VLM service.

        Args:
            case_data: Case dictionary from ExcelExtractor

        Returns:
            Enriched case data with VL/VLM descriptions
        """
        logger.info(f"Processing images for case {case_data['case_id']} (async VLM)")

        # Collect all images across all issues
        all_images = []
        for issue in case_data['issues']:
            all_images.extend(issue['images'])

        logger.info(f"   Total images: {len(all_images)}")

        if not all_images:
            logger.info("   No images to process")
            return case_data

        if not self.enabled:
            logger.info("   VLM processing disabled - adding empty VL fields")
            self._add_empty_vl_fields(all_images)
            return case_data

        if not self.service_available:
            logger.warning("   VLM service not available - adding empty VL fields")
            self._add_empty_vl_fields(all_images)
            return case_data

        # Process images with VLM service
        client = VLMServiceClient(base_url=self.vlm_service_url)

        processed_count = 0
        failed_count = 0

        # Process images concurrently (with limit)
        semaphore = asyncio.Semaphore(self.max_workers)

        async def process_with_limit(img: Dict) -> Dict:
            async with semaphore:
                return await self._process_image_vlm(client, img)

        tasks = [process_with_limit(img) for img in all_images]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for img, result in zip(all_images, results):
            if isinstance(result, Exception):
                logger.warning(f"   Failed to process {img['image_id']}: {result}")
                self._add_empty_vl_fields([img])
                failed_count += 1
            else:
                # Merge VLM result into image data
                img.update(result)
                processed_count += 1

        await client.close()

        logger.info(f"   Processed: {processed_count} images")
        if failed_count > 0:
            logger.warning(f"   Failed: {failed_count} images")

        # Add case-level VLM metadata
        case_data['vlm_processed'] = True
        case_data['vlm_processed_count'] = processed_count

        return case_data

    async def _process_image_vlm(self, client: "VLMServiceClient", image_data: Dict) -> Dict:
        """
        Process single image with external VLM service.

        Args:
            client: VLMServiceClient instance
            image_data: Image metadata dict

        Returns:
            VLM analysis results mapped to image fields
        """
        image_path = Path(image_data['file_path'])

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        options = VLMJobOptions(
            analysis_depth=AnalysisDepth.DETAILED,
            output_language=self.language,
            include_ocr=True
        )

        try:
            result = await client.analyze_file(
                image_path,
                prompt_template="mold_defect_analysis",
                options=options,
                timeout=120
            )

            # Map VLM result to image fields
            return {
                'vl_description': result.document_summary or result.defect_details or '',
                'defect_type': result.defect_type or '',
                'equipment_part': result.equipment_part or '',
                'text_in_image': result.text_in_image or '',
                'visual_annotations': result.visual_annotations or '',
                'severity': result.severity or '',
                'vlm_confidence': result.metadata.confidence_score,
                'vlm_job_id': result.job_id,
                'key_insights': result.key_insights,
                'suggested_actions': result.suggested_actions,
                'tags': result.tags
            }

        except Exception as e:
            logger.warning(f"VLM analysis failed for {image_data['image_id']}: {e}")
            raise

    def _enrich_case_legacy(self, case_data: Dict) -> Dict:
        """
        Legacy synchronous VL processing using local service.

        Args:
            case_data: Case dictionary from ExcelExtractor

        Returns:
            Enriched case data with VL descriptions
        """
        logger.info(f"Processing images for case {case_data['case_id']} (legacy)")

        # Collect all images across all issues
        all_images = []
        for issue in case_data['issues']:
            all_images.extend(issue['images'])

        logger.info(f"   Total images: {len(all_images)}")

        if not all_images:
            logger.info("   No images to process")
            return case_data

        # If VL is disabled, just add empty VL fields and return
        if not self.enabled:
            logger.info("   VL processing disabled - adding empty VL fields")
            self._add_empty_vl_fields(all_images)
            return case_data

        # Process images in parallel
        processed_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all image processing tasks
            futures = {
                executor.submit(self._process_image_legacy, img): img
                for img in all_images
            }

            # Process results with progress bar
            for future in tqdm(
                as_completed(futures),
                total=len(all_images),
                desc="VL Processing",
                unit="img"
            ):
                img = futures[future]
                try:
                    vl_result = future.result()

                    # Enrich image data with VL results
                    img['vl_description'] = vl_result.get('detailed_description', '')
                    img['defect_type'] = vl_result.get('defect_type', '')
                    img['equipment_part'] = vl_result.get('equipment_part', '')
                    img['text_in_image'] = vl_result.get('text_in_image', '')
                    img['visual_annotations'] = vl_result.get('visual_annotations', '')

                    processed_count += 1

                except Exception as e:
                    logger.warning(f"   Failed to process {img['image_id']}: {e}")
                    # Set default values for failed images
                    img['vl_description'] = "Image processing failed"
                    img['defect_type'] = ''
                    img['equipment_part'] = ''
                    img['text_in_image'] = ''
                    img['visual_annotations'] = ''
                    failed_count += 1

        logger.info(f"   Processed: {processed_count} images")
        if failed_count > 0:
            logger.warning(f"   Failed: {failed_count} images")

        return case_data

    def _process_image_legacy(self, image_data: Dict, max_retries: int = 3) -> Dict:
        """
        Send single image to legacy VL service for analysis.

        Args:
            image_data: Image metadata dict
            max_retries: Number of retry attempts

        Returns:
            VL analysis results
        """
        image_path = Path(image_data['file_path'])

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Retry logic for transient failures
        for attempt in range(max_retries):
            try:
                with open(image_path, 'rb') as f:
                    files = {
                        'file': (image_path.name, f, 'image/jpeg')
                    }
                    params = {
                        'language': self.language
                    }

                    response = requests.post(
                        f"{self.vl_service_url}/analyze-image",
                        files=files,
                        params=params,
                        timeout=60  # VL processing can take time
                    )

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"Timeout on {image_data['image_id']}, retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Request error on {image_data['image_id']}, retrying...")
                    time.sleep(2 ** attempt)
                else:
                    raise

        # Should not reach here
        raise Exception("Max retries exceeded")

    def _add_empty_vl_fields(self, images: List[Dict]) -> None:
        """Add empty VL fields to images when processing is disabled"""
        for img in images:
            img['vl_description'] = ''
            img['defect_type'] = ''
            img['equipment_part'] = ''
            img['text_in_image'] = ''
            img['visual_annotations'] = ''
            img['severity'] = ''
            img['vlm_confidence'] = 0.0
            img['key_insights'] = []
            img['suggested_actions'] = []
            img['tags'] = []

    def process_single_image(self, image_path: str) -> Dict:
        """
        Process a single image file (convenience method for testing).

        Args:
            image_path: Path to image file

        Returns:
            VL analysis results
        """
        image_data = {
            'image_id': Path(image_path).stem,
            'file_path': image_path
        }

        if self.use_vlm_service:
            return asyncio.run(self._process_single_image_async(image_data))
        else:
            return self._process_image_legacy(image_data)

    async def _process_single_image_async(self, image_data: Dict) -> Dict:
        """Process single image with VLM service (async)"""
        client = VLMServiceClient(base_url=self.vlm_service_url)
        try:
            result = await self._process_image_vlm(client, image_data)
            return result
        finally:
            await client.close()

    def enrich_with_vlm_result(self, case_data: Dict, vlm_result: "VLMResult") -> Dict:
        """
        Merge VLM insights into case structure.

        Args:
            case_data: Case data from ExcelExtractor
            vlm_result: VLM analysis result

        Returns:
            Enriched case data with VLM metadata
        """
        # Add case-level VLM metadata
        case_data['vlm_summary'] = vlm_result.document_summary
        case_data['key_insights'] = vlm_result.key_insights
        case_data['tags'] = vlm_result.tags
        case_data['vlm_confidence'] = vlm_result.metadata.confidence_score
        case_data['vlm_job_id'] = vlm_result.job_id
        case_data['vlm_processed'] = True

        # Add analysis metadata
        if vlm_result.analysis:
            case_data['analysis'] = {
                'sentiment': vlm_result.analysis.sentiment,
                'topics': vlm_result.analysis.topics,
                'entities': vlm_result.analysis.entities,
                'complexity_score': vlm_result.analysis.complexity_score
            }

        # Map extracted images to issue images
        if vlm_result.extracted_images:
            for extracted in vlm_result.extracted_images:
                # Try to match by image_id or page number
                for issue in case_data.get('issues', []):
                    for img in issue.get('images', []):
                        if img.get('image_id') == extracted.image_id:
                            img['vl_description'] = extracted.description
                            img['defect_type'] = extracted.defect_type or ''
                            if extracted.insights:
                                img['insights'] = extracted.insights

        return case_data


# Convenience function
def enrich_with_vl(
    case_data: Dict,
    vl_service_url: str = "http://localhost:8083",
    enabled: bool = False,
    use_vlm_service: bool = True
) -> Dict:
    """
    Quick enrichment function.

    Args:
        case_data: Case data from ExcelExtractor
        vl_service_url: VL service URL
        enabled: Enable VL processing (default: False)
        use_vlm_service: Use external VLM service (default: True)

    Returns:
        Enriched case data
    """
    processor = VLProcessor(
        vl_service_url=vl_service_url,
        enabled=enabled,
        use_vlm_service=use_vlm_service
    )
    return processor.enrich_case(case_data)


if __name__ == "__main__":
    # Test with extracted case
    import sys

    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = "data/troubleshooting/processed/TS-1947688-ED736A0501.json"

    print(f"Testing VL processing with: {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        case = json.load(f)

    processor = VLProcessor(enabled=True)
    enriched = processor.enrich_case(case)

    print(f"\nVL processing complete")
    print(f"   Case: {enriched['case_id']}")
    print(f"   VLM processed: {enriched.get('vlm_processed', False)}")

    # Show sample VL results
    for issue in enriched['issues']:
        if issue['images']:
            img = issue['images'][0]
            if img.get('vl_description'):
                print(f"\n   Sample VL description:")
                print(f"   Image: {img['image_id']}")
                print(f"   Defect: {img['defect_type']}")
                print(f"   Description: {img['vl_description'][:100]}...")
                break
