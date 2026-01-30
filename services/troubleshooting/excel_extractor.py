#!/usr/bin/env python3
"""
Excel Troubleshooting Case Extractor

Extracts structured data and embedded images from troubleshooting Excel files.
Handles complex Excel layouts with metadata sections and data tables.

Usage:
    from services.troubleshooting.excel_extractor import ExcelTroubleshootingExtractor

    extractor = ExcelTroubleshootingExtractor(output_dir=Path("data/troubleshooting/processed"))
    case_data = extractor.extract_case(excel_path)
"""

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XLImage
from PIL import Image
import io
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExcelTroubleshootingExtractor:
    """Extract structured data and images from troubleshooting Excel files"""

    def __init__(self, output_dir: Path):
        """
        Initialize extractor.

        Args:
            output_dir: Directory for processed output (JSON + images)
        """
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ExcelExtractor initialized: output={self.output_dir}")

    def extract_case(self, excel_path: Path) -> Dict:
        """
        Extract complete troubleshooting case from Excel file.

        Args:
            excel_path: Path to Excel file

        Returns:
            dict with case metadata, issues, and images
        """
        excel_path = Path(excel_path)

        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        logger.info(f"📄 Processing: {excel_path.name}")

        try:
            # Load workbook with openpyxl for images and metadata
            wb = load_workbook(excel_path, data_only=True)
            sheet = wb.active

            logger.info(f"   Sheet: {sheet.title}, Rows: {sheet.max_row}, Cols: {sheet.max_column}")

            # Step 1: Extract metadata from header rows
            metadata = self._extract_metadata(sheet, excel_path)

            # Step 2: Extract data table (find header row automatically)
            header_row = self._find_data_table_header(sheet)
            logger.info(f"   Data table starts at row {header_row + 1}")

            df = pd.read_excel(excel_path, sheet_name=0, header=header_row)
            df_clean = df.dropna(subset=['NO', '問題点'], how='all')

            # Remove duplicate header rows that sometimes appear in data
            df_clean = df_clean[df_clean['NO'] != 'NO']

            # Step 3: Extract and map images
            image_map = self._extract_images(sheet, excel_path.stem)
            logger.info(f"   Extracted {len(image_map)} images")

            # Step 4: Build issues list with mapped images
            issues = self._build_issues(df_clean, image_map, metadata)
            logger.info(f"   Found {len(issues)} troubleshooting issues")

            # Step 5: Build case structure
            case_id = self._generate_case_id(metadata)

            case = {
                "case_id": case_id,
                "metadata": metadata,
                "issues": issues,
                "total_issues": len(issues),
                "source_file": str(excel_path),
                "extraction_version": "1.0"
            }

            # Save to JSON
            json_path = self.output_dir / f"{case_id}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(case, f, ensure_ascii=False, indent=2)

            logger.info(f"   ✅ Saved to {json_path.name}")

            return case

        except Exception as e:
            logger.error(f"   ❌ Error processing {excel_path.name}: {e}")
            raise

    def _extract_metadata(self, sheet, excel_path: Path) -> Dict:
        """Extract case metadata from header rows (1-19)"""

        def safe_get(cell_ref):
            """Safely get cell value"""
            try:
                val = sheet[cell_ref].value
                return str(val).strip() if val not in (None, '') else None
            except:
                return None

        metadata = {
            "part_number": safe_get('F6'),
            "internal_number": safe_get('F8'),
            "mold_type": safe_get('F4'),
            "material_t0": safe_get('G13'),
            "material_t1": safe_get('I13'),
            "material_t2": safe_get('K13'),
            "color": safe_get('G14'),
            "molding_machine": safe_get('G19'),
            "source_filename": excel_path.name
        }

        return metadata

    def _find_data_table_header(self, sheet) -> int:
        """
        Find the row where the data table starts by looking for column headers.

        Returns:
            Row index (0-based for pandas) where data table header is located
        """
        # Look for the row containing key column headers
        key_headers = ['NO', '問題点', '原因，对策', '型试']

        for row_idx in range(15, 30):  # Check rows 15-30
            row_values = []
            for col_idx in range(1, 15):  # Check first 14 columns
                cell_value = sheet.cell(row=row_idx, column=col_idx).value
                if cell_value:
                    row_values.append(str(cell_value))

            # Check if this row contains the key headers
            matches = sum(1 for header in key_headers if any(header in val for val in row_values))

            if matches >= 3:  # At least 3 key headers found
                return row_idx - 1  # Return 0-indexed row for pandas

        # Default to row 19 (0-indexed) if not found
        logger.warning("Could not auto-detect data table header, using default row 19")
        return 19

    def _extract_images(self, sheet, case_stem: str) -> Dict:
        """
        Extract all embedded images from sheet and save to files.

        Args:
            sheet: openpyxl worksheet
            case_stem: Case filename stem for naming images

        Returns:
            dict mapping image index to {image_id, file_path, row, col}
        """
        image_map = {}

        if not hasattr(sheet, '_images') or not sheet._images:
            return image_map

        for idx, img in enumerate(sheet._images, 1):
            # Skip first image (usually company logo in header)
            if idx == 1:
                continue

            # Get image position
            row, col = 0, 0
            if hasattr(img, 'anchor') and hasattr(img.anchor, '_from'):
                row = img.anchor._from.row + 1  # 1-indexed
                col = img.anchor._from.col + 1

            # Generate image ID and filename
            image_id = f"{case_stem}_img{idx:03d}"
            image_filename = f"{image_id}.jpg"
            image_path = self.images_dir / image_filename

            try:
                # Get image data and convert to PIL
                img_data = img._data()
                pil_image = Image.open(io.BytesIO(img_data))

                # Convert to RGB if needed
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')

                # Save as JPEG
                pil_image.save(image_path, "JPEG", quality=90)

                image_map[idx] = {
                    "image_id": image_id,
                    "file_path": str(image_path),
                    "row": row,
                    "col": col
                }

            except Exception as e:
                logger.warning(f"Failed to extract image {idx}: {e}")

        return image_map

    def _build_issues(self, df: pd.DataFrame, image_map: Dict, metadata: Dict) -> List[Dict]:
        """
        Build issues list from data table with mapped images.

        Args:
            df: Cleaned DataFrame with issue data
            image_map: Extracted images mapped to positions
            metadata: Case metadata

        Returns:
            List of issue dictionaries
        """
        issues = []

        for idx, row in df.iterrows():
            # Skip if NO is not a valid number
            try:
                issue_num = int(row['NO'])
            except (ValueError, TypeError):
                continue

            # Build issue record
            issue = {
                "issue_number": issue_num,
                "trial_version": str(row['型试']) if pd.notna(row['型试']) else None,
                "category": str(row['项目']) if pd.notna(row['项目']) else None,
                "problem": str(row['問題点']).strip() if pd.notna(row['問題点']) else "",
                "solution": str(row['原因，对策']).strip() if pd.notna(row['原因，对策']) else "",
                "result_t1": str(row['修正結果T1']) if pd.notna(row['修正結果T1']) else None,
                "result_t2": str(row['修正結果T2']) if pd.notna(row['修正結果T2']) else None,
                "cause_classification": str(row['原因分类']) if pd.notna(row['原因分类']) and '原因分类' in row else None,
                "images": []
            }

            # Map images to this issue
            # Convert pandas index to Excel row (approximate)
            excel_row = idx + 22  # Adjust based on header offset

            # Find images within ±15 rows of this issue
            for img_idx, img_data in image_map.items():
                if abs(img_data['row'] - excel_row) <= 15:
                    issue['images'].append({
                        "image_id": img_data['image_id'],
                        "file_path": img_data['file_path'],
                        "cell_location": f"Row {img_data['row']}, Col {img_data['col']}",
                        "vl_description": None,  # To be filled by VL processor
                        "defect_type": None,
                        "text_in_image": None
                    })

            issues.append(issue)

        return issues

    def _generate_case_id(self, metadata: Dict) -> str:
        """Generate unique case ID from metadata"""

        part_num = metadata.get('part_number') or 'UNKNOWN'
        internal_num = metadata.get('internal_number') or str(uuid.uuid4())[:8]

        case_id = f"TS-{part_num}-{internal_num}"

        return case_id


# Convenience function for quick extraction
def extract_troubleshooting_case(excel_path: str, output_dir: str = "data/troubleshooting/processed") -> Dict:
    """
    Quick extraction function.

    Args:
        excel_path: Path to Excel file
        output_dir: Output directory

    Returns:
        Extracted case data
    """
    extractor = ExcelTroubleshootingExtractor(Path(output_dir))
    return extractor.extract_case(Path(excel_path))


if __name__ == "__main__":
    # Test with sample file
    import sys

    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
    else:
        excel_file = "docs/1947688(ED736A0501)-case.xlsx"

    print(f"Testing extraction with: {excel_file}")
    case = extract_troubleshooting_case(excel_file)
    print(f"\n✅ Extracted case: {case['case_id']}")
    print(f"   Issues: {case['total_issues']}")
    print(f"   Images: {sum(len(issue['images']) for issue in case['issues'])}")
