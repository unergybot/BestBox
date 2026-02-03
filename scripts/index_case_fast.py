#!/usr/bin/env python3
"""Simple script to index troubleshooting case without VLM enrichment."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import json
import logging
from services.troubleshooting.excel_extractor import ExcelTroubleshootingExtractor
from services.troubleshooting.indexer import TroubleshootingIndexer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def index_case_only(excel_path: str, output_dir: str = "data/troubleshooting/processed"):
    """Extract and index case without VLM enrichment (fast)."""
    excel_path = Path(excel_path)
    output_dir = Path(output_dir)
    
    logger.info(f"🚀 Processing: {excel_path.name}")
    
    # 1. Extract
    logger.info("Step 1: Extracting Excel...")
    extractor = ExcelTroubleshootingExtractor(output_dir=output_dir)
    case_data = extractor.extract_case(excel_path)
    
    total_images = sum(len(issue.get('images', [])) for issue in case_data['issues'])
    logger.info(f"✅ Extracted: {case_data['total_issues']} issues, {total_images} images")
    
    # 2. Index (no VLM enrichment - faster)
    logger.info("Step 2: Indexing to Qdrant...")
    indexer = TroubleshootingIndexer()
    stats = indexer.index_case(case_data)
    
    logger.info(f"✅ Indexed: {stats['case_points']} case points, {stats['issue_points']} issue points")
    logger.info("🎉 Done! Ready for UI verification.")
    
    return case_data, stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("excel_path", help="Path to Excel file")
    parser.add_argument("--output", default="data/troubleshooting/processed")
    
    args = parser.parse_args()
    index_case_only(args.excel_path, args.output)
