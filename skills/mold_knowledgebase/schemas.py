"""
Pydantic models for mold knowledgebase skill validation.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
import re


class UploadMoldCaseInput(BaseModel):
    """Input schema for upload_mold_case tool."""

    file_path: str = Field(
        ...,
        description="Path to the .xlsx file"
    )
    index_immediately: bool = Field(
        default=True,
        description="Whether to index into Qdrant immediately"
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate that the file path ends with .xlsx"""
        if not v.endswith(".xlsx"):
            raise ValueError("File must be an .xlsx file")
        return v


class UpdateCaseMetadataInput(BaseModel):
    """Input schema for update_case_metadata tool."""

    case_id: str = Field(
        ...,
        description="Case ID to update (format: TS-{part_number}-{internal_number})"
    )
    metadata: Dict[str, Any] = Field(
        ...,
        description="Metadata fields to update"
    )

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: str) -> str:
        """Validate case ID format."""
        if not v.startswith("TS-"):
            raise ValueError("Case ID must start with 'TS-'")
        return v


class AddIssueImagesInput(BaseModel):
    """Input schema for add_issue_images tool."""

    case_id: str = Field(
        ...,
        description="Case ID containing the issue"
    )
    issue_number: int = Field(
        ...,
        ge=1,
        description="Issue number within the case"
    )
    image_paths: List[str] = Field(
        ...,
        min_length=1,
        description="Paths to image files"
    )
    run_vl_analysis: bool = Field(
        default=True,
        description="Run vision-language analysis on images"
    )

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: str) -> str:
        if not v.startswith("TS-"):
            raise ValueError("Case ID must start with 'TS-'")
        return v


class CreateIssueRecordInput(BaseModel):
    """Input schema for create_issue_record tool."""

    case_id: str = Field(
        ...,
        description="Case ID to add the issue to"
    )
    problem: str = Field(
        ...,
        min_length=1,
        description="Problem description"
    )
    solution: str = Field(
        ...,
        min_length=1,
        description="Solution description"
    )
    trial_version: Optional[Literal["T0", "T1", "T2", "T3"]] = Field(
        default=None,
        description="Trial version stage"
    )
    result_t1: Optional[str] = Field(
        default=None,
        description="T1 trial result"
    )
    result_t2: Optional[str] = Field(
        default=None,
        description="T2 trial result"
    )
    category: Optional[str] = Field(
        default=None,
        description="Issue category"
    )
    defect_types: Optional[List[str]] = Field(
        default=None,
        description="List of defect type classifications"
    )

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: str) -> str:
        if not v.startswith("TS-"):
            raise ValueError("Case ID must start with 'TS-'")
        return v


class BatchIndexCasesInput(BaseModel):
    """Input schema for batch_index_cases tool."""

    directory_path: str = Field(
        ...,
        description="Directory containing .xlsx files"
    )
    skip_existing: bool = Field(
        default=True,
        description="Skip cases that are already indexed"
    )
    run_vl_analysis: bool = Field(
        default=False,
        description="Run VL analysis on extracted images"
    )


# Response models

class UploadMoldCaseResult(BaseModel):
    """Result schema for upload_mold_case tool."""

    success: bool
    case_id: str
    total_issues: int
    source_file: str
    indexed: bool
    indexing_stats: Optional[Dict[str, int]] = None
    error: Optional[str] = None


class UpdateCaseMetadataResult(BaseModel):
    """Result schema for update_case_metadata tool."""

    success: bool
    case_id: str
    updated_fields: List[str]
    error: Optional[str] = None


class AddIssueImagesResult(BaseModel):
    """Result schema for add_issue_images tool."""

    success: bool
    case_id: str
    issue_number: int
    images_added: int
    vl_processed: bool
    error: Optional[str] = None


class CreateIssueRecordResult(BaseModel):
    """Result schema for create_issue_record tool."""

    success: bool
    case_id: str
    issue_id: str
    issue_number: int
    indexed: bool
    error: Optional[str] = None


class BatchIndexCasesResult(BaseModel):
    """Result schema for batch_index_cases tool."""

    success: bool
    indexed_count: int
    skipped_count: int
    failed_count: int
    failed_files: List[str] = []
    error: Optional[str] = None


# Image metadata model

class ImageMetadata(BaseModel):
    """Image metadata stored in Qdrant."""

    image_id: str
    file_path: str
    vl_description: Optional[str] = None
    defect_type: Optional[str] = None
    text_in_image: Optional[str] = None
    equipment_part: Optional[str] = None
    visual_annotations: Optional[str] = None
    cell_location: Optional[str] = None


# Issue model

class IssueRecord(BaseModel):
    """Issue record model."""

    issue_id: str
    case_id: str
    issue_number: int
    trial_version: Optional[str] = None
    category: Optional[str] = None
    problem: str
    solution: str
    result_t1: Optional[str] = None
    result_t2: Optional[str] = None
    cause_classification: Optional[str] = None
    has_images: bool = False
    image_count: int = 0
    images: List[ImageMetadata] = []
    defect_types: List[str] = []
    combined_text: str = ""


# Case model

class CaseRecord(BaseModel):
    """Case record model."""

    case_id: str
    part_number: Optional[str] = None
    internal_number: Optional[str] = None
    mold_type: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    total_issues: int = 0
    issue_ids: List[int] = []
    source_file: str
    text_summary: str = ""
