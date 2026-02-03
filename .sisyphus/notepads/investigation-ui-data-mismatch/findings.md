# Investigation: UI Showing Wrong Solutions/Images for Troubleshooting Query

## Issue Description
Query: "产品披锋怎么解决？"
- Backend search returns correct results with proper images
- UI displays wrong solutions and wrong images (not matching the issues)

## Root Cause Identified

### Location
- File: `/home/apexai/BestBox/agents/context_manager.py`
- Lines: 30, 74-91

### Problem
The context manager truncates tool results at 1500 characters (`MAX_TOOL_RESULT_CHARS = 1500`).

Troubleshooting search returns JSON ~4400+ characters for typical queries (3 results with images).

Truncation method (lines 88-91):
```python
half = max_chars // 2 - 20  # = 730 chars
truncated = f"{content[:half]}\n\n[... {len(content) - max_chars} chars truncated ...]\n\n{content[-half:]}"
```

### Impact
For 4426-character JSON:
- Keeps first 730 chars: Query metadata, partial case_id
- **DISCARDS middle 2966 chars**: All `solution` fields, most `images` arrays
- Keeps last 730 chars: End of last result

The LLM receives broken JSON and hallucinates missing content.

### Why Wrong Solutions/Images
- `solution` field content is in truncated middle
- `images` array with `image_id` to `image_url` mapping is truncated
- LLM tries to reconstruct JSON but produces incorrect data

## Data Flow

1. Tool `search_troubleshooting_kb()` returns complete JSON (lines 136-194)
2. `ToolMessage` created with full JSON content
3. Agent calls `apply_sliding_window()` (mold_agent.py line 156)
4. Context manager truncates `ToolMessage.content` if >1500 chars
5. LLM receives broken JSON, tries to fix it
6. Agent outputs incorrect JSON in response
7. Frontend parses and displays wrong data

## Recommended Fix

Modify `truncate_tool_result()` in `context_manager.py`:
1. Detect if content is JSON (starts with `{`, parses as JSON)
2. For JSON content, skip truncation or use much higher limit (e.g., 10000 chars)
3. Alternative: Parse JSON, truncate individual results, re-serialize

## Files Involved

- `/home/apexai/BestBox/agents/context_manager.py` - Truncation logic (ROOT CAUSE)
- `/home/apexai/BestBox/tools/troubleshooting_tools.py` - Returns JSON (CORRECT)
- `/home/apexai/BestBox/agents/mold_agent.py` - Uses sliding window (calls truncation)
- `/home/apexai/BestBox/frontend/copilot-demo/lib/troubleshooting-detector.ts` - Parses agent response
