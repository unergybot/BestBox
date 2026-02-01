"""
Mold Knowledgebase Skill Hook Handlers

Provides lifecycle hooks for:
- BEFORE_TOOL_CALL: Validate mold KB tool inputs
- AFTER_TOOL_CALL: Log indexing operations
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# List of mold KB tool names to monitor
MOLD_KB_TOOLS = {
    "upload_mold_case",
    "update_case_metadata",
    "add_issue_images",
    "create_issue_record",
    "batch_index_cases",
}


def validate_mold_tool_input(context) -> Optional[Dict[str, Any]]:
    """
    Hook that validates input before mold KB tool calls.

    Called on BEFORE_TOOL_CALL event to check:
    - File paths exist for upload operations
    - Case ID format is valid
    - Required parameters are present

    Args:
        context: HookContext with event, state, plugin_name, metadata
            - context.metadata.get("tool_name"): Name of the tool being called
            - context.metadata.get("tool_args"): Arguments passed to the tool

    Returns:
        None to continue, or dict with error to block the call
    """
    tool_name = context.metadata.get("tool_name", "")

    # Only process mold KB tools
    if tool_name not in MOLD_KB_TOOLS:
        return None

    tool_args = context.metadata.get("tool_args", {})

    logger.debug(f"[Mold KB Hook] Validating {tool_name} with args: {tool_args}")

    # Validate upload_mold_case
    if tool_name == "upload_mold_case":
        file_path = tool_args.get("file_path")
        if file_path:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"[Mold KB Hook] File not found: {file_path}")
                # We don't block here - let the tool handle the error
                # This is just logging for visibility

            if not file_path.endswith(".xlsx"):
                logger.warning(f"[Mold KB Hook] Invalid file extension: {file_path}")

    # Validate case_id format for relevant tools
    if tool_name in {"update_case_metadata", "add_issue_images", "create_issue_record"}:
        case_id = tool_args.get("case_id", "")
        if case_id and not case_id.startswith("TS-"):
            logger.warning(f"[Mold KB Hook] Invalid case_id format: {case_id}")

    # Validate batch_index_cases directory
    if tool_name == "batch_index_cases":
        directory_path = tool_args.get("directory_path")
        if directory_path:
            path = Path(directory_path)
            if not path.exists():
                logger.warning(f"[Mold KB Hook] Directory not found: {directory_path}")
            elif not path.is_dir():
                logger.warning(f"[Mold KB Hook] Path is not a directory: {directory_path}")

    # Validate add_issue_images image paths
    if tool_name == "add_issue_images":
        image_paths = tool_args.get("image_paths", [])
        for img_path in image_paths:
            path = Path(img_path)
            if not path.exists():
                logger.warning(f"[Mold KB Hook] Image not found: {img_path}")

    return None  # Continue with tool call


def log_indexing_operation(context) -> Optional[Dict[str, Any]]:
    """
    Hook that logs after mold KB tool calls complete.

    Called on AFTER_TOOL_CALL event to:
    - Log successful indexing operations
    - Track metrics for monitoring
    - Record audit trail

    Args:
        context: HookContext with event, state, plugin_name, metadata
            - context.metadata.get("tool_name"): Name of the tool that was called
            - context.metadata.get("tool_result"): Result from the tool

    Returns:
        None (logging only, no state modification)
    """
    tool_name = context.metadata.get("tool_name", "")

    # Only process mold KB tools
    if tool_name not in MOLD_KB_TOOLS:
        return None

    tool_result = context.metadata.get("tool_result", {})

    # Handle case where tool_result is a string (error message)
    if isinstance(tool_result, str):
        logger.info(f"[Mold KB Audit] {tool_name} returned string result")
        return None

    # Extract common fields
    success = tool_result.get("success", False)
    case_id = tool_result.get("case_id", "")
    error = tool_result.get("error")

    timestamp = datetime.utcnow().isoformat()

    if success:
        # Log successful operations by type
        if tool_name == "upload_mold_case":
            total_issues = tool_result.get("total_issues", 0)
            indexed = tool_result.get("indexed", False)
            logger.info(
                f"[Mold KB Audit] {timestamp} | UPLOAD | case={case_id} | "
                f"issues={total_issues} | indexed={indexed}"
            )

        elif tool_name == "update_case_metadata":
            updated_fields = tool_result.get("updated_fields", [])
            logger.info(
                f"[Mold KB Audit] {timestamp} | UPDATE_METADATA | case={case_id} | "
                f"fields={updated_fields}"
            )

        elif tool_name == "add_issue_images":
            issue_number = tool_result.get("issue_number", 0)
            images_added = tool_result.get("images_added", 0)
            vl_processed = tool_result.get("vl_processed", False)
            logger.info(
                f"[Mold KB Audit] {timestamp} | ADD_IMAGES | case={case_id} | "
                f"issue={issue_number} | images={images_added} | vl={vl_processed}"
            )

        elif tool_name == "create_issue_record":
            issue_id = tool_result.get("issue_id", "")
            issue_number = tool_result.get("issue_number", 0)
            logger.info(
                f"[Mold KB Audit] {timestamp} | CREATE_ISSUE | case={case_id} | "
                f"issue_id={issue_id} | number={issue_number}"
            )

        elif tool_name == "batch_index_cases":
            indexed_count = tool_result.get("indexed_count", 0)
            skipped_count = tool_result.get("skipped_count", 0)
            failed_count = tool_result.get("failed_count", 0)
            logger.info(
                f"[Mold KB Audit] {timestamp} | BATCH_INDEX | "
                f"indexed={indexed_count} | skipped={skipped_count} | failed={failed_count}"
            )

    else:
        # Log failures
        logger.warning(
            f"[Mold KB Audit] {timestamp} | FAILED | tool={tool_name} | "
            f"case={case_id} | error={error}"
        )

    return None  # No state modification
