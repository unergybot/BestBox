#!/usr/bin/env python3
"""
VL Processor for Troubleshooting Images

Enriches extracted images with Vision-Language model descriptions.
Processes images through Qwen3-VL-8B to extract defect information.

Usage:
    from services.troubleshooting.vl_processor import VLProcessor

    processor = VLProcessor()
    enriched_case = processor.enrich_case(case_data)
"""

import requests
from pathlib import Path
from typing import Dict, List
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VLProcessor:
    """Process images with Qwen3-VL and enrich issue data"""

    def __init__(
        self,
        vl_service_url: str = "http://localhost:8083",
        max_workers: int = 4,
        language: str = "zh",
        enabled: bool = False  # Disabled by default due to ROCm compatibility issues
    ):
        """
        Initialize VL processor.

        Args:
            vl_service_url: URL of VL service
            max_workers: Max concurrent VL requests
            language: Output language ('zh' or 'en')
            enabled: Enable VL processing (disabled by default)
        """
        self.vl_service_url = vl_service_url
        self.max_workers = max_workers
        self.language = language
        self.enabled = enabled
        self.service_available = False

        if not enabled:
            logger.info("🔕 VL processing DISABLED (text-only search mode)")
            logger.info("   Images will be extracted and stored, but not analyzed")
            return

        # Check service health only if enabled
        try:
            response = requests.get(f"{vl_service_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ VL service connected: {vl_service_url}")
                self.service_available = True
            else:
                logger.warning(f"⚠️  VL service returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️  VL service not available at {vl_service_url}")
            logger.warning("   Images will be processed when service becomes available")

    def enrich_case(self, case_data: Dict) -> Dict:
        """
        Add VL descriptions to all images in a case.

        Args:
            case_data: Case dictionary from ExcelExtractor

        Returns:
            Enriched case data with VL descriptions (or empty VL fields if disabled)
        """
        logger.info(f"🔍 Processing images for case {case_data['case_id']}")

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
            logger.info("   ⏭️  VL processing disabled - adding empty VL fields")
            for img in all_images:
                img['vl_description'] = ''
                img['defect_type'] = ''
                img['equipment_part'] = ''
                img['text_in_image'] = ''
                img['visual_annotations'] = ''
            return case_data

        # Process images in parallel
        processed_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all image processing tasks
            futures = {
                executor.submit(self._process_image, img): img
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

        logger.info(f"   ✅ Processed: {processed_count} images")
        if failed_count > 0:
            logger.warning(f"   ⚠️  Failed: {failed_count} images")

        return case_data

    def _process_image(self, image_data: Dict, max_retries: int = 3) -> Dict:
        """
        Send single image to VL service for analysis.

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

        return self._process_image(image_data)


# Convenience function
def enrich_with_vl(
    case_data: Dict,
    vl_service_url: str = "http://localhost:8083",
    enabled: bool = False
) -> Dict:
    """
    Quick enrichment function.

    Args:
        case_data: Case data from ExcelExtractor
        vl_service_url: VL service URL
        enabled: Enable VL processing (default: False)

    Returns:
        Enriched case data (with empty VL fields if disabled)
    """
    processor = VLProcessor(vl_service_url=vl_service_url, enabled=enabled)
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

    processor = VLProcessor()
    enriched = processor.enrich_case(case)

    print(f"\n✅ VL processing complete")
    print(f"   Case: {enriched['case_id']}")

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
