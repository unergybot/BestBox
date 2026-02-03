#!/usr/bin/env python3
"""
VLM Enrichment and Indexing Pipeline script.

Orchestrates the full pipeline for a single case:
1. Extract data from Excel (Issues + Images)
2. Enrich images using VLM Service (Async)
3. Index enriched data into Qdrant (Case + Issues collections)

Usage:
    python scripts/enrich_and_index_case.py docs/MyCase.xlsx [--limit 5]
"""

import sys
import asyncio
import argparse
import logging
from pathlib import Path
import json

# Add project root to python path to allow imports from services
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from services.troubleshooting.excel_extractor import ExcelTroubleshootingExtractor
from services.troubleshooting.validation_pipeline import ValidationPipeline
from services.troubleshooting.vl_processor import VLProcessor
from services.troubleshooting.indexer import TroubleshootingIndexer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("EnrichPipeline")

async def process_case_pipeline(
    excel_path: Path,
    output_dir: Path,
    limit: int = 0,
    validate_mappings: bool = False
):
    """
    Run the full extraction -> enrichment -> indexing pipeline.
    """
    if not excel_path.exists():
        logger.error(f"File not found: {excel_path}")
        return

    logger.info(f"🚀 Starting pipeline for: {excel_path.name}")
    
    # 1. Extraction
    logger.info("--- Step 1: Excel Extraction ---")
    extractor = ExcelTroubleshootingExtractor(output_dir=output_dir)
    try:
        case_data = extractor.extract_case(excel_path)
        logger.info(f"✅ Extracted case {case_data['case_id']} with {case_data['total_issues']} issues")
        
        # Apply limit if requested
        if limit > 0:
            logger.info(f"✂️  Applying limit: processing only first {limit} images")
            image_count = 0
            # Iterate issues and keep images until limit is reached
            for issue in case_data['issues']:
                if image_count >= limit:
                    issue['images'] = []
                    continue
                
                remaining = limit - image_count
                if len(issue['images']) > remaining:
                    issue['images'] = issue['images'][:remaining]
                
                image_count += len(issue['images'])
            
            logger.info(f"   Reduced to {image_count} images for testing")
            
    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        return

    # 1.5 Mapping validation (optional)
    if validate_mappings:
        try:
            validation_pipeline = ValidationPipeline(output_dir=output_dir)
            case_data = await validation_pipeline.validate_case(excel_path, case_data)
        except Exception as e:
            logger.warning(f"⚠️  Mapping validation failed: {e}")

    # 2. VLM Enrichment
    logger.info("--- Step 2: VLM Enrichment ---")
    # Enable VLM and use external service
    processor = VLProcessor(enabled=True, use_vlm_service=True)
    
    try:
        enriched_case = await processor.enrich_case_async(case_data)
        
        vlm_count = enriched_case.get('vlm_processed_count', 0)
        logger.info(f"✅ VLM Enrichment complete. Processed {vlm_count} images.")
        
        # Save enriched JSON for inspection
        json_path = output_dir / f"{enriched_case['case_id']}_enriched.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(enriched_case, f, ensure_ascii=False, indent=2)
        logger.info(f"   Saved enriched JSON to {json_path}")
        
    except Exception as e:
        logger.error(f"❌ VLM Enrichment failed: {e}")
        return

    # 3. Indexing
    logger.info("--- Step 3: Qdrant Indexing ---")
    indexer = TroubleshootingIndexer()
    
    try:
        stats = indexer.index_case(enriched_case)
        logger.info(f"✅ Indexing complete.")
        logger.info(f"   Case Points: {stats['case_points']}")
        logger.info(f"   Issue Points: {stats['issue_points']}")
    except Exception as e:
        logger.error(f"❌ Indexing failed: {e}")
        return

    logger.info("🎉 Pipeline completed successfully!")

def main():
    parser = argparse.ArgumentParser(description="Extract, Enrich, and Index a Troubleshooting Case")
    parser.add_argument("excel_path", type=str, help="Path to the Excel file")
    parser.add_argument("--output", type=str, default="data/troubleshooting/processed", help="Output directory for processed files")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of images to process (0 for all)")
    parser.add_argument("--validate-mappings", action="store_true", help="Run VLM mapping validation")
    
    args = parser.parse_args()
    
    excel_file = Path(args.excel_path)
    output_dir = Path(args.output)
    
    # Run async pipeline
    asyncio.run(
        process_case_pipeline(
            excel_file,
            output_dir,
            limit=args.limit,
            validate_mappings=args.validate_mappings
        )
    )

if __name__ == "__main__":
    main()
