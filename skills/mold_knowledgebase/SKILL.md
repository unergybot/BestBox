---
name: mold-knowledgebase
description: Manage mold troubleshooting knowledge base - metadata, images, issue records
version: 1.0.0
author: BestBox Team
requires:
  bins: []
  python_packages:
    - openpyxl
    - qdrant_client
    - pydantic
  env_vars: []
tools:
  - name: upload_mold_case
    description: Upload an Excel troubleshooting case file and index it into the knowledge base
    parameters:
      type: object
      properties:
        file_path:
          type: string
          description: Path to the .xlsx file
        index_immediately:
          type: boolean
          description: Whether to index into Qdrant immediately
          default: true
      required:
        - file_path

  - name: update_case_metadata
    description: Update metadata fields for an existing case
    parameters:
      type: object
      properties:
        case_id:
          type: string
          description: Case ID to update
        metadata:
          type: object
          description: Metadata fields to update (part_number, material, mold_type, color, etc.)
      required:
        - case_id
        - metadata

  - name: add_issue_images
    description: Add or link images to a specific issue
    parameters:
      type: object
      properties:
        case_id:
          type: string
          description: Case ID containing the issue
        issue_number:
          type: integer
          description: Issue number within the case
        image_paths:
          type: array
          items:
            type: string
          description: Paths to image files
        run_vl_analysis:
          type: boolean
          description: Run vision-language analysis on images
          default: true
      required:
        - case_id
        - issue_number
        - image_paths

  - name: create_issue_record
    description: Create a new issue record in an existing case
    parameters:
      type: object
      properties:
        case_id:
          type: string
          description: Case ID to add the issue to
        problem:
          type: string
          description: Problem description
        solution:
          type: string
          description: Solution description
        trial_version:
          type: string
          enum: ["T0", "T1", "T2", "T3"]
          description: Trial version stage
        result_t1:
          type: string
          description: T1 trial result
        result_t2:
          type: string
          description: T2 trial result
        category:
          type: string
          description: Issue category
        defect_types:
          type: array
          items:
            type: string
          description: List of defect type classifications
      required:
        - case_id
        - problem
        - solution

  - name: batch_index_cases
    description: Batch index multiple case files from a directory
    parameters:
      type: object
      properties:
        directory_path:
          type: string
          description: Directory containing .xlsx files
        skip_existing:
          type: boolean
          description: Skip cases that are already indexed
          default: true
        run_vl_analysis:
          type: boolean
          description: Run VL analysis on extracted images
          default: false
      required:
        - directory_path

hooks:
  - event: BEFORE_TOOL_CALL
    handler: skills.mold_knowledgebase.handlers.validate_mold_tool_input
    priority: 50
  - event: AFTER_TOOL_CALL
    handler: skills.mold_knowledgebase.handlers.log_indexing_operation
    priority: 100
---

# Mold Knowledgebase Skill

Provides tools for managing the mold troubleshooting knowledge base including:

- **Metadata management**: Update case and issue metadata fields
- **Image handling**: Link images to issues with optional VL analysis
- **Issue records**: Create, update, and manage troubleshooting issues
- **Batch operations**: Bulk index from directories

## Data Model

### Case (troubleshooting_cases collection)
- `case_id`: Unique case identifier (format: TS-{part_number}-{internal_number})
- `part_number`: Product part number
- `internal_number`: Internal tracking number
- `mold_type`: Type of mold
- `material`: Material specification (T0/T1/T2)
- `color`: Product color
- `total_issues`: Number of issues in the case
- `issue_ids[]`: List of issue numbers
- `source_file`: Original Excel file path
- `text_summary`: Searchable text summary

### Issue (troubleshooting_issues collection)
- `issue_id`: Unique issue identifier (format: {case_id}-{issue_number})
- `case_id`: Parent case ID
- `issue_number`: Sequential issue number within case
- `problem`: Problem description
- `solution`: Solution/countermeasure description
- `trial_version`: Trial stage (T0, T1, T2, T3)
- `result_t1`: T1 modification result
- `result_t2`: T2 modification result
- `category`: Issue category classification
- `defect_types[]`: List of defect type classifications
- `has_images`: Boolean indicating if images are attached
- `images[]`: Array of image metadata objects

### Image Metadata
- `image_id`: Unique image identifier
- `file_path`: Path to image file
- `vl_description`: Vision-language model description
- `defect_type`: Detected defect type
- `text_in_image`: OCR text from image
- `equipment_part`: Identified equipment/part
- `visual_annotations`: Additional visual annotations

## Usage Examples

### Upload a New Case
```python
from skills.mold_knowledgebase import upload_mold_case

result = upload_mold_case(
    file_path="/path/to/troubleshooting.xlsx",
    index_immediately=True
)
print(f"Indexed case: {result['case_id']}")
```

### Update Case Metadata
```python
from skills.mold_knowledgebase import update_case_metadata

result = update_case_metadata(
    case_id="TS-1947688-ED736A0501",
    metadata={
        "material": "ABS+PC",
        "color": "Black"
    }
)
```

### Batch Index Directory
```python
from skills.mold_knowledgebase import batch_index_cases

result = batch_index_cases(
    directory_path="/data/troubleshooting/xlsx/",
    skip_existing=True,
    run_vl_analysis=False
)
print(f"Indexed {result['indexed_count']} cases")
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDINGS_URL` | `http://localhost:8081` | BGE-M3 embeddings service URL |
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant server port |
| `VL_SERVICE_URL` | `http://localhost:8083` | Vision-language service URL |
| `VL_ENABLED` | `false` | Enable VL processing |

## Collections

This skill manages two Qdrant collections:

1. **troubleshooting_cases**: Case-level vectors for broad search
2. **troubleshooting_issues**: Issue-level vectors for precise search

Both use BGE-M3 1024-dimensional embeddings with cosine similarity.
