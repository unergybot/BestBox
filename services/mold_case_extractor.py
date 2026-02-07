"""
Mold case extractor — processes Docling Serve structured output
to extract mold troubleshooting cases from Excel reports.

Mold troubleshooting Excel files contain tabular case data:
defect type, mold number, solution, root cause, images.
This module maps Docling's table/image structures to domain-specific
case records suitable for Qdrant indexing.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Column name aliases (Chinese / English) → canonical field names
COLUMN_ALIASES: Dict[str, str] = {
    # Defect type
    "defect_type": "defect_type",
    "defect type": "defect_type",
    "缺陷类型": "defect_type",
    "不良类型": "defect_type",
    "问题类型": "defect_type",
    # Mold ID
    "mold_id": "mold_id",
    "mold id": "mold_id",
    "mold_number": "mold_id",
    "mold number": "mold_id",
    "模具编号": "mold_id",
    "模号": "mold_id",
    # Description
    "description": "description",
    "问题描述": "description",
    "缺陷描述": "description",
    "不良描述": "description",
    "现象": "description",
    "issue": "description",
    "problem": "description",
    # Solution
    "solution": "solution",
    "解决方案": "solution",
    "措施": "solution",
    "对策": "solution",
    "corrective_action": "solution",
    "corrective action": "solution",
    # Root cause
    "root_cause": "root_cause",
    "root cause": "root_cause",
    "原因分析": "root_cause",
    "根本原因": "root_cause",
    "原因": "root_cause",
    # Severity
    "severity": "severity",
    "严重程度": "severity",
    "等级": "severity",
    "level": "severity",
    # Category
    "category": "solution_category",
    "solution_category": "solution_category",
    "分类": "solution_category",
    "类别": "solution_category",
}

SEVERITY_ALIASES: Dict[str, str] = {
    "high": "high",
    "严重": "high",
    "重大": "high",
    "medium": "medium",
    "中等": "medium",
    "一般": "medium",
    "low": "low",
    "轻微": "low",
    "minor": "low",
}


class MoldCase:
    """A single mold troubleshooting case record."""

    def __init__(
        self,
        defect_type: str = "",
        mold_id: str = "",
        description: str = "",
        solution: str = "",
        root_cause: str = "",
        severity: str = "medium",
        solution_category: str = "",
        images: Optional[List[str]] = None,
        raw_row: Optional[Dict[str, str]] = None,
    ):
        self.case_id = str(uuid.uuid4())
        self.defect_type = defect_type
        self.mold_id = mold_id
        self.description = description
        self.solution = solution
        self.root_cause = root_cause
        self.severity = SEVERITY_ALIASES.get(severity.lower().strip(), "medium")
        self.solution_category = solution_category
        self.images = images or []
        self.raw_row = raw_row or {}

    def to_chunk_text(self) -> str:
        """Render as a single text chunk for embedding."""
        parts = []
        if self.defect_type:
            parts.append(f"Defect Type: {self.defect_type}")
        if self.mold_id:
            parts.append(f"Mold ID: {self.mold_id}")
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.root_cause:
            parts.append(f"Root Cause: {self.root_cause}")
        if self.solution:
            parts.append(f"Solution: {self.solution}")
        if self.severity:
            parts.append(f"Severity: {self.severity}")
        if self.solution_category:
            parts.append(f"Category: {self.solution_category}")
        return "\n".join(parts)

    def to_metadata(self, source_file: str, uploaded_by: str = "") -> Dict[str, Any]:
        """Return Qdrant payload metadata for this case."""
        return {
            "doc_id": self.case_id,
            "source_file": source_file,
            "file_type": "xlsx",
            "domain": "mold",
            "defect_type": self.defect_type,
            "mold_id": self.mold_id,
            "solution_category": self.solution_category,
            "severity": self.severity,
            "has_images": len(self.images) > 0,
            "image_paths": self.images,
            "uploaded_by": uploaded_by,
            "upload_date": datetime.now(timezone.utc).isoformat(),
            "processing_method": "docling",
        }


class MoldCaseExtractor:
    """
    Extracts mold troubleshooting cases from Docling Serve structured output.

    Usage:
        extractor = MoldCaseExtractor()
        cases = extractor.extract(docling_result, source_file="report.xlsx")
    """

    def __init__(self, image_output_dir: str = "data/uploads/images"):
        self.image_output_dir = Path(image_output_dir)
        self.image_output_dir.mkdir(parents=True, exist_ok=True)

    def extract(
        self,
        docling_result: Dict[str, Any],
        source_file: str = "",
        uploaded_by: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Extract cases from Docling Serve JSON output.

        Returns a list of dicts, each containing:
          - text: the chunk text (for embedding)
          - metadata: the Qdrant payload
        """
        tables = self._extract_tables(docling_result)
        images = self._extract_images(docling_result)

        if not tables:
            # No tables found — fall back to a single-chunk document
            text = self._extract_text(docling_result)
            if not text:
                logger.warning(f"No tables or text found in Docling result for {source_file}")
                return []
            return [
                {
                    "text": text,
                    "metadata": {
                        "doc_id": str(uuid.uuid4()),
                        "source_file": source_file,
                        "file_type": Path(source_file).suffix.lstrip("."),
                        "domain": "mold",
                        "uploaded_by": uploaded_by,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                        "processing_method": "docling",
                        "has_images": len(images) > 0,
                    },
                }
            ]

        # Process each table for case-per-row extraction
        cases: List[Dict[str, Any]] = []
        for table in tables:
            cases.extend(
                self._extract_cases_from_table(table, images, source_file, uploaded_by)
            )

        logger.info(
            f"Extracted {len(cases)} cases from {source_file} "
            f"({len(tables)} tables, {len(images)} images)"
        )
        return cases

    # ------------------------------------------------------------------
    # Table processing
    # ------------------------------------------------------------------

    def _extract_cases_from_table(
        self,
        table: Dict[str, Any],
        images: List[Dict[str, Any]],
        source_file: str,
        uploaded_by: str,
    ) -> List[Dict[str, Any]]:
        """Extract cases from a single Docling table structure."""
        rows = table.get("data", [])
        headers = table.get("headers", [])

        if not rows:
            return []

        # Map headers to canonical field names
        col_map = self._map_columns(headers)

        cases = []
        for row_idx, row in enumerate(rows):
            fields: Dict[str, str] = {}
            raw_row: Dict[str, str] = {}

            for col_idx, cell_value in enumerate(row):
                cell_str = str(cell_value).strip() if cell_value else ""
                if col_idx < len(headers):
                    raw_row[headers[col_idx]] = cell_str
                    canonical = col_map.get(col_idx)
                    if canonical:
                        fields[canonical] = cell_str

            # Skip empty rows
            if not any(fields.values()):
                continue

            case = MoldCase(
                defect_type=fields.get("defect_type", ""),
                mold_id=fields.get("mold_id", ""),
                description=fields.get("description", ""),
                solution=fields.get("solution", ""),
                root_cause=fields.get("root_cause", ""),
                severity=fields.get("severity", "medium"),
                solution_category=fields.get("solution_category", ""),
                raw_row=raw_row,
            )

            chunk = {
                "text": case.to_chunk_text(),
                "metadata": case.to_metadata(source_file, uploaded_by),
            }
            chunk["metadata"]["chunk_index"] = row_idx
            cases.append(chunk)

        return cases

    def _map_columns(self, headers: List[str]) -> Dict[int, str]:
        """Map column indices to canonical field names via aliases."""
        col_map: Dict[int, str] = {}
        for idx, header in enumerate(headers):
            normalized = header.strip().lower().replace(" ", "_")
            canonical = COLUMN_ALIASES.get(normalized)
            if not canonical:
                # Try partial match
                canonical = COLUMN_ALIASES.get(header.strip().lower())
            if canonical:
                col_map[idx] = canonical
        return col_map

    # ------------------------------------------------------------------
    # Docling result parsing helpers
    # ------------------------------------------------------------------

    def _extract_tables(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Pull table structures from Docling's JSON output."""
        tables = []

        # Docling v2 format: result.document.tables[]
        doc = result.get("document", result)
        if "tables" in doc:
            for tbl in doc["tables"]:
                headers = tbl.get("headers", tbl.get("column_headers", []))
                data = tbl.get("data", tbl.get("rows", []))
                tables.append({"headers": headers, "data": data})

        # Also check for tables in content items
        for item in doc.get("content", []):
            if item.get("type") == "table":
                headers = item.get("headers", item.get("column_headers", []))
                data = item.get("data", item.get("rows", []))
                tables.append({"headers": headers, "data": data})

        return tables

    def _extract_images(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Pull embedded images from Docling's JSON output."""
        images = []
        doc = result.get("document", result)

        # Docling embeds images as base64 or provides file paths
        for item in doc.get("pictures", doc.get("images", [])):
            images.append({
                "data": item.get("data", item.get("image", "")),
                "format": item.get("format", item.get("mimetype", "image/png")),
                "page": item.get("page", 0),
                "caption": item.get("caption", ""),
            })

        # Also look in content items
        for item in doc.get("content", []):
            if item.get("type") == "picture":
                images.append({
                    "data": item.get("data", item.get("image", "")),
                    "format": item.get("format", "image/png"),
                    "page": item.get("page", 0),
                    "caption": item.get("caption", ""),
                })

        return images

    def _extract_text(self, result: Dict[str, Any]) -> str:
        """Extract plain text / markdown from Docling result."""
        doc = result.get("document", result)

        # Try markdown output first
        if "md" in result:
            return result["md"]

        # Concatenate content items
        parts = []
        for item in doc.get("content", []):
            text = item.get("text", "")
            if text:
                parts.append(text)

        return "\n\n".join(parts)
