"""
Mold Knowledgebase Skill

Provides tools for managing the mold troubleshooting knowledge base:
- upload_mold_case: Upload and index Excel troubleshooting files
- update_case_metadata: Update case metadata fields
- add_issue_images: Link images to issues
- create_issue_record: Create new issue records
- batch_index_cases: Bulk index from directories
"""

import os
import logging
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct

from .schemas import (
    UploadMoldCaseInput,
    UpdateCaseMetadataInput,
    AddIssueImagesInput,
    CreateIssueRecordInput,
    BatchIndexCasesInput,
    UploadMoldCaseResult,
    UpdateCaseMetadataResult,
    AddIssueImagesResult,
    CreateIssueRecordResult,
    BatchIndexCasesResult,
)

logger = logging.getLogger(__name__)

# Configuration from environment
EMBEDDINGS_URL = os.getenv("EMBEDDINGS_URL", "http://localhost:8081")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
VL_SERVICE_URL = os.getenv("VL_SERVICE_URL", "http://localhost:8083")
VL_ENABLED = os.getenv("VL_ENABLED", "false").lower() == "true"
OUTPUT_DIR = os.getenv("TROUBLESHOOTING_OUTPUT_DIR", "data/troubleshooting/processed")


def _get_qdrant_client() -> QdrantClient:
    """Get configured Qdrant client."""
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def _get_extractor():
    """Lazy import of ExcelTroubleshootingExtractor."""
    from services.troubleshooting.excel_extractor import ExcelTroubleshootingExtractor
    return ExcelTroubleshootingExtractor(Path(OUTPUT_DIR))


def _get_indexer():
    """Lazy import of TroubleshootingIndexer."""
    from services.troubleshooting.indexer import TroubleshootingIndexer
    return TroubleshootingIndexer(
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
        embeddings_url=EMBEDDINGS_URL
    )


def _get_vl_processor():
    """Lazy import of VLProcessor."""
    from services.troubleshooting.vl_processor import VLProcessor
    return VLProcessor(
        vl_service_url=VL_SERVICE_URL,
        enabled=VL_ENABLED
    )


def _get_embedder():
    """Lazy import of TroubleshootingEmbedder."""
    from services.troubleshooting.embedder import TroubleshootingEmbedder
    return TroubleshootingEmbedder(embeddings_url=EMBEDDINGS_URL)


def upload_mold_case(
    file_path: str,
    index_immediately: bool = True
) -> Dict[str, Any]:
    """
    Upload an Excel troubleshooting case file and index it into the knowledge base.

    Args:
        file_path: Path to the .xlsx file
        index_immediately: Whether to index into Qdrant immediately

    Returns:
        Result dict with case_id, total_issues, indexed status
    """
    try:
        # Validate input
        validated = UploadMoldCaseInput(
            file_path=file_path,
            index_immediately=index_immediately
        )

        file_path = Path(validated.file_path)
        if not file_path.exists():
            return UploadMoldCaseResult(
                success=False,
                case_id="",
                total_issues=0,
                source_file=str(file_path),
                indexed=False,
                error=f"File not found: {file_path}"
            ).model_dump()

        # Extract case data
        extractor = _get_extractor()
        case_data = extractor.extract_case(file_path)

        logger.info(f"Extracted case: {case_data['case_id']} with {case_data['total_issues']} issues")

        # Optionally run VL analysis
        if VL_ENABLED:
            vl_processor = _get_vl_processor()
            case_data = vl_processor.enrich_case(case_data)

        indexing_stats = None
        indexed = False

        # Index if requested
        if validated.index_immediately:
            indexer = _get_indexer()
            indexing_stats = indexer.index_case(case_data)
            indexed = True
            logger.info(f"Indexed case: {indexing_stats}")

        return UploadMoldCaseResult(
            success=True,
            case_id=case_data['case_id'],
            total_issues=case_data['total_issues'],
            source_file=str(file_path),
            indexed=indexed,
            indexing_stats=indexing_stats
        ).model_dump()

    except Exception as e:
        logger.error(f"Error uploading mold case: {e}", exc_info=True)
        return UploadMoldCaseResult(
            success=False,
            case_id="",
            total_issues=0,
            source_file=file_path if isinstance(file_path, str) else str(file_path),
            indexed=False,
            error=str(e)
        ).model_dump()


def update_case_metadata(
    case_id: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update metadata fields for an existing case.

    Args:
        case_id: Case ID to update (format: TS-{part_number}-{internal_number})
        metadata: Metadata fields to update

    Returns:
        Result dict with success status and updated fields
    """
    try:
        # Validate input
        validated = UpdateCaseMetadataInput(
            case_id=case_id,
            metadata=metadata
        )

        client = _get_qdrant_client()

        # Find the case point
        search_result = client.scroll(
            collection_name="troubleshooting_cases",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="case_id",
                        match=MatchValue(value=validated.case_id)
                    )
                ]
            ),
            limit=1
        )

        points, _ = search_result
        if not points:
            return UpdateCaseMetadataResult(
                success=False,
                case_id=validated.case_id,
                updated_fields=[],
                error=f"Case not found: {validated.case_id}"
            ).model_dump()

        point = points[0]
        point_id = point.id

        # Update payload with new metadata
        updated_fields = list(validated.metadata.keys())
        client.set_payload(
            collection_name="troubleshooting_cases",
            payload=validated.metadata,
            points=[point_id]
        )

        logger.info(f"Updated case {validated.case_id}: {updated_fields}")

        return UpdateCaseMetadataResult(
            success=True,
            case_id=validated.case_id,
            updated_fields=updated_fields
        ).model_dump()

    except Exception as e:
        logger.error(f"Error updating case metadata: {e}", exc_info=True)
        return UpdateCaseMetadataResult(
            success=False,
            case_id=case_id,
            updated_fields=[],
            error=str(e)
        ).model_dump()


def add_issue_images(
    case_id: str,
    issue_number: int,
    image_paths: List[str],
    run_vl_analysis: bool = True
) -> Dict[str, Any]:
    """
    Add or link images to a specific issue.

    Args:
        case_id: Case ID containing the issue
        issue_number: Issue number within the case
        image_paths: Paths to image files
        run_vl_analysis: Run vision-language analysis on images

    Returns:
        Result dict with success status and images added count
    """
    try:
        # Validate input
        validated = AddIssueImagesInput(
            case_id=case_id,
            issue_number=issue_number,
            image_paths=image_paths,
            run_vl_analysis=run_vl_analysis
        )

        client = _get_qdrant_client()
        issue_id = f"{validated.case_id}-{validated.issue_number}"

        # Find the issue point
        search_result = client.scroll(
            collection_name="troubleshooting_issues",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="issue_id",
                        match=MatchValue(value=issue_id)
                    )
                ]
            ),
            limit=1
        )

        points, _ = search_result
        if not points:
            return AddIssueImagesResult(
                success=False,
                case_id=validated.case_id,
                issue_number=validated.issue_number,
                images_added=0,
                vl_processed=False,
                error=f"Issue not found: {issue_id}"
            ).model_dump()

        point = points[0]
        point_id = point.id
        existing_images = point.payload.get("images", [])

        # Process new images
        new_images = []
        vl_processed = False

        for img_path in validated.image_paths:
            path = Path(img_path)
            if not path.exists():
                logger.warning(f"Image not found: {img_path}")
                continue

            image_id = f"{validated.case_id}_img{len(existing_images) + len(new_images) + 1:03d}"

            image_data = {
                "image_id": image_id,
                "file_path": str(path),
                "vl_description": None,
                "defect_type": None,
                "text_in_image": None,
                "equipment_part": None,
                "visual_annotations": None
            }

            # Run VL analysis if enabled and requested
            if validated.run_vl_analysis and VL_ENABLED:
                try:
                    vl_processor = _get_vl_processor()
                    if vl_processor.service_available:
                        vl_result = vl_processor._process_image(image_data)
                        image_data.update({
                            "vl_description": vl_result.get("detailed_description", ""),
                            "defect_type": vl_result.get("defect_type", ""),
                            "text_in_image": vl_result.get("text_in_image", ""),
                            "equipment_part": vl_result.get("equipment_part", ""),
                            "visual_annotations": vl_result.get("visual_annotations", "")
                        })
                        vl_processed = True
                except Exception as vl_err:
                    logger.warning(f"VL processing failed for {img_path}: {vl_err}")

            new_images.append(image_data)

        # Update issue with new images
        all_images = existing_images + new_images
        client.set_payload(
            collection_name="troubleshooting_issues",
            payload={
                "images": all_images,
                "has_images": len(all_images) > 0,
                "image_count": len(all_images)
            },
            points=[point_id]
        )

        logger.info(f"Added {len(new_images)} images to issue {issue_id}")

        return AddIssueImagesResult(
            success=True,
            case_id=validated.case_id,
            issue_number=validated.issue_number,
            images_added=len(new_images),
            vl_processed=vl_processed
        ).model_dump()

    except Exception as e:
        logger.error(f"Error adding issue images: {e}", exc_info=True)
        return AddIssueImagesResult(
            success=False,
            case_id=case_id,
            issue_number=issue_number,
            images_added=0,
            vl_processed=False,
            error=str(e)
        ).model_dump()


def create_issue_record(
    case_id: str,
    problem: str,
    solution: str,
    trial_version: Optional[str] = None,
    result_t1: Optional[str] = None,
    result_t2: Optional[str] = None,
    category: Optional[str] = None,
    defect_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a new issue record in an existing case.

    Args:
        case_id: Case ID to add the issue to
        problem: Problem description
        solution: Solution description
        trial_version: Trial version stage (T0, T1, T2, T3)
        result_t1: T1 trial result
        result_t2: T2 trial result
        category: Issue category
        defect_types: List of defect type classifications

    Returns:
        Result dict with success status and issue details
    """
    try:
        # Validate input
        validated = CreateIssueRecordInput(
            case_id=case_id,
            problem=problem,
            solution=solution,
            trial_version=trial_version,
            result_t1=result_t1,
            result_t2=result_t2,
            category=category,
            defect_types=defect_types
        )

        client = _get_qdrant_client()

        # Find the case to get metadata
        case_result = client.scroll(
            collection_name="troubleshooting_cases",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="case_id",
                        match=MatchValue(value=validated.case_id)
                    )
                ]
            ),
            limit=1
        )

        case_points, _ = case_result
        if not case_points:
            return CreateIssueRecordResult(
                success=False,
                case_id=validated.case_id,
                issue_id="",
                issue_number=0,
                indexed=False,
                error=f"Case not found: {validated.case_id}"
            ).model_dump()

        case_point = case_points[0]
        case_payload = case_point.payload

        # Determine next issue number
        existing_issue_ids = case_payload.get("issue_ids", [])
        next_issue_number = max(existing_issue_ids) + 1 if existing_issue_ids else 1
        issue_id = f"{validated.case_id}-{next_issue_number}"

        # Build issue data
        issue_data = {
            "issue_id": issue_id,
            "case_id": validated.case_id,
            "part_number": case_payload.get("part_number"),
            "internal_number": case_payload.get("internal_number"),
            "issue_number": next_issue_number,
            "trial_version": validated.trial_version,
            "category": validated.category,
            "problem": validated.problem,
            "solution": validated.solution,
            "result_t1": validated.result_t1,
            "result_t2": validated.result_t2,
            "cause_classification": None,
            "has_images": False,
            "image_count": 0,
            "images": [],
            "defect_types": validated.defect_types or [],
            "combined_text": f"{validated.problem} {validated.solution}"
        }

        # Generate embedding
        embedder = _get_embedder()
        embedding = embedder.create_issue_embedding(issue_data)

        # Create point and upsert
        point_id = str(uuid.uuid4())
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=issue_data
        )

        client.upsert(
            collection_name="troubleshooting_issues",
            points=[point]
        )

        # Update case with new issue
        updated_issue_ids = existing_issue_ids + [next_issue_number]
        client.set_payload(
            collection_name="troubleshooting_cases",
            payload={
                "issue_ids": updated_issue_ids,
                "total_issues": len(updated_issue_ids)
            },
            points=[case_point.id]
        )

        logger.info(f"Created issue {issue_id} in case {validated.case_id}")

        return CreateIssueRecordResult(
            success=True,
            case_id=validated.case_id,
            issue_id=issue_id,
            issue_number=next_issue_number,
            indexed=True
        ).model_dump()

    except Exception as e:
        logger.error(f"Error creating issue record: {e}", exc_info=True)
        return CreateIssueRecordResult(
            success=False,
            case_id=case_id,
            issue_id="",
            issue_number=0,
            indexed=False,
            error=str(e)
        ).model_dump()


def batch_index_cases(
    directory_path: str,
    skip_existing: bool = True,
    run_vl_analysis: bool = False
) -> Dict[str, Any]:
    """
    Batch index multiple case files from a directory.

    Args:
        directory_path: Directory containing .xlsx files
        skip_existing: Skip cases that are already indexed
        run_vl_analysis: Run VL analysis on extracted images

    Returns:
        Result dict with counts of indexed, skipped, and failed files
    """
    try:
        # Validate input
        validated = BatchIndexCasesInput(
            directory_path=directory_path,
            skip_existing=skip_existing,
            run_vl_analysis=run_vl_analysis
        )

        dir_path = Path(validated.directory_path)
        if not dir_path.exists():
            return BatchIndexCasesResult(
                success=False,
                indexed_count=0,
                skipped_count=0,
                failed_count=0,
                error=f"Directory not found: {dir_path}"
            ).model_dump()

        # Find all xlsx files
        xlsx_files = list(dir_path.glob("*.xlsx"))
        if not xlsx_files:
            return BatchIndexCasesResult(
                success=True,
                indexed_count=0,
                skipped_count=0,
                failed_count=0,
                error="No .xlsx files found in directory"
            ).model_dump()

        logger.info(f"Found {len(xlsx_files)} .xlsx files in {dir_path}")

        # Get existing case IDs if skipping
        existing_case_ids = set()
        if validated.skip_existing:
            client = _get_qdrant_client()
            try:
                scroll_result = client.scroll(
                    collection_name="troubleshooting_cases",
                    limit=1000,
                    with_payload=["case_id"]
                )
                points, _ = scroll_result
                existing_case_ids = {p.payload.get("case_id") for p in points if p.payload}
                logger.info(f"Found {len(existing_case_ids)} existing cases")
            except Exception:
                logger.warning("Could not check existing cases, will process all")

        indexed_count = 0
        skipped_count = 0
        failed_count = 0
        failed_files = []

        extractor = _get_extractor()
        indexer = _get_indexer()
        vl_processor = None
        if validated.run_vl_analysis and VL_ENABLED:
            vl_processor = _get_vl_processor()

        for xlsx_file in xlsx_files:
            try:
                # Extract case
                case_data = extractor.extract_case(xlsx_file)
                case_id = case_data['case_id']

                # Check if should skip
                if validated.skip_existing and case_id in existing_case_ids:
                    logger.info(f"Skipping existing case: {case_id}")
                    skipped_count += 1
                    continue

                # Run VL analysis if enabled
                if vl_processor:
                    case_data = vl_processor.enrich_case(case_data)

                # Index
                indexer.index_case(case_data)
                indexed_count += 1
                logger.info(f"Indexed: {case_id}")

            except Exception as e:
                logger.error(f"Failed to process {xlsx_file.name}: {e}")
                failed_count += 1
                failed_files.append(str(xlsx_file.name))

        logger.info(f"Batch indexing complete: {indexed_count} indexed, {skipped_count} skipped, {failed_count} failed")

        return BatchIndexCasesResult(
            success=True,
            indexed_count=indexed_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            failed_files=failed_files
        ).model_dump()

    except Exception as e:
        logger.error(f"Error in batch indexing: {e}", exc_info=True)
        return BatchIndexCasesResult(
            success=False,
            indexed_count=0,
            skipped_count=0,
            failed_count=0,
            error=str(e)
        ).model_dump()


def register(api):
    """
    Register skill tools with the plugin API.

    Args:
        api: PluginAPI instance
    """
    api.register_tool(
        name="upload_mold_case",
        description="Upload an Excel troubleshooting case file and index it into the knowledge base",
        func=upload_mold_case,
    )

    api.register_tool(
        name="update_case_metadata",
        description="Update metadata fields for an existing case",
        func=update_case_metadata,
    )

    api.register_tool(
        name="add_issue_images",
        description="Add or link images to a specific issue",
        func=add_issue_images,
    )

    api.register_tool(
        name="create_issue_record",
        description="Create a new issue record in an existing case",
        func=create_issue_record,
    )

    api.register_tool(
        name="batch_index_cases",
        description="Batch index multiple case files from a directory",
        func=batch_index_cases,
    )

    api.log_info("Mold Knowledgebase skill registered with 5 tools")
