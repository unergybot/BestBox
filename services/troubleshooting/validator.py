"""
Troubleshooting Response Validator

Validates LLM responses to filter out hallucinated case_ids.
This prevents the LLM from fabricating fake cases.
"""

import json
import re
import logging
from typing import Set, Optional, Tuple
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

# Cache valid case_ids to avoid repeated Qdrant queries
_valid_case_ids_cache: Optional[Set[str]] = None


def get_valid_case_ids(qdrant_host: str = "localhost", qdrant_port: int = 6333) -> Set[str]:
    """
    Get all valid case_ids from Qdrant.
    Results are cached for performance.
    """
    global _valid_case_ids_cache

    if _valid_case_ids_cache is not None:
        return _valid_case_ids_cache

    try:
        qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Get all unique case_ids from troubleshooting_issues
        valid_ids = set()

        # Scroll through all points to get case_ids
        offset = None
        while True:
            results, offset = qdrant.scroll(
                collection_name="troubleshooting_issues",
                limit=100,
                offset=offset,
                with_payload=["case_id"]
            )

            for point in results:
                if point.payload and "case_id" in point.payload:
                    valid_ids.add(point.payload["case_id"])

            if offset is None:
                break

        # Also check troubleshooting_cases collection
        offset = None
        while True:
            results, offset = qdrant.scroll(
                collection_name="troubleshooting_cases",
                limit=100,
                offset=offset,
                with_payload=["case_id"]
            )

            for point in results:
                if point.payload and "case_id" in point.payload:
                    valid_ids.add(point.payload["case_id"])

            if offset is None:
                break

        _valid_case_ids_cache = valid_ids
        logger.info(f"Cached {len(valid_ids)} valid case_ids from Qdrant")
        return valid_ids

    except Exception as e:
        logger.error(f"Failed to get valid case_ids: {e}")
        return set()


def clear_case_id_cache():
    """Clear the cached case_ids (call after indexing new data)"""
    global _valid_case_ids_cache
    _valid_case_ids_cache = None
    logger.info("Cleared case_id cache")


def extract_json_from_response(response: str) -> Tuple[Optional[dict], str, str]:
    """
    Extract JSON block from LLM response.

    Returns:
        (parsed_json, prefix_text, suffix_text)
    """
    # Find ```json ... ``` block
    pattern = r'```json\s*([\s\S]*?)\s*```'
    match = re.search(pattern, response)

    if not match:
        return None, response, ""

    json_str = match.group(1)
    prefix = response[:match.start()]
    suffix = response[match.end():]

    try:
        parsed = json.loads(json_str)
        return parsed, prefix, suffix
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from response: {e}")
        return None, response, ""


def validate_and_filter_results(response: str) -> str:
    """
    Validate LLM response and filter out hallucinated case_ids.

    Args:
        response: The raw LLM response containing JSON

    Returns:
        Cleaned response with only valid case_ids
    """
    parsed, prefix, suffix = extract_json_from_response(response)

    if parsed is None:
        logger.warning("No valid JSON found in response, returning as-is")
        return response

    if "results" not in parsed or not isinstance(parsed["results"], list):
        logger.warning("No 'results' array in JSON, returning as-is")
        return response

    # Get valid case_ids
    valid_ids = get_valid_case_ids()

    if not valid_ids:
        logger.warning("No valid case_ids in cache, skipping validation")
        return response

    # Filter results
    original_count = len(parsed["results"])
    valid_results = []
    removed_count = 0

    for result in parsed["results"]:
        case_id = result.get("case_id", "")

        if case_id in valid_ids:
            valid_results.append(result)
        else:
            removed_count += 1
            logger.warning(f"Filtered out hallucinated case_id: {case_id}")

    if removed_count > 0:
        logger.info(f"Filtered {removed_count}/{original_count} hallucinated results")

        # Update the parsed JSON
        parsed["results"] = valid_results
        parsed["total_found"] = len(valid_results)

        # Add a note about filtering
        if "_validation" not in parsed:
            parsed["_validation"] = {
                "original_count": original_count,
                "filtered_count": removed_count,
                "reason": "hallucinated_case_ids_removed"
            }

        # Reconstruct the response
        new_json = json.dumps(parsed, ensure_ascii=False, indent=2)
        return f"{prefix}```json\n{new_json}\n```{suffix}"

    return response


def validate_case_id(case_id: str) -> bool:
    """Check if a single case_id is valid"""
    valid_ids = get_valid_case_ids()
    return case_id in valid_ids


# Preload cache on module import
def _preload_cache():
    """Preload the cache in background"""
    try:
        get_valid_case_ids()
    except Exception:
        pass  # Ignore errors during preload

# Don't preload automatically - let it be lazy
# _preload_cache()
