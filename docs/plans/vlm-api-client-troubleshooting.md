# VLM Mapping Validation API - Client Integration Guide & Troubleshooting

**Date:** 2026-02-02
**Version:** 1.0.1

---

## Quick Reference

| Method | Endpoint | Content-Type | Description |
|--------|----------|--------------|-------------|
| POST | `/api/v1/validate-mappings` | `multipart/form-data` | Single page validation |
| POST | `/api/v1/validate-mappings/batch` | `application/json` | Batch validation (max 10 pages) |
| GET | `/api/v1/validate-mappings/{job_id}` | - | Get job status/result |
| GET | `/api/v1/validate-mappings` | - | List all jobs |
| DELETE | `/api/v1/validate-mappings/{job_id}` | - | Delete a job |

**Base URL:** `http://192.168.1.196:8081`

---

## Common Issues & Solutions

### Issue 1: "400 Bad Request" or "Failed to decode JSON"

**Cause:** Wrong Content-Type header or malformed JSON

**Solution:**
```python
# ✅ Correct - Use application/json for batch
import requests

response = requests.post(
    "http://192.168.1.196:8081/api/v1/validate-mappings/batch",
    json={
        "case_id": "TS-ABC123-001",
        "pages": [...]
    },
    headers={"Content-Type": "application/json"}
)

# ❌ Wrong - Don't use data= with JSON
response = requests.post(
    "http://192.168.1.196:8081/api/v1/validate-mappings/batch",
    data='{"case_id": "test", "pages": []}',  # This might cause issues
    headers={"Content-Type": "application/json"}
)
```

### Issue 2: "MISSING_PAGE_IMAGE" (400)

**Cause:** For single page validation, `page_image` is required in `multipart/form-data`

**Solution:**
```python
# ✅ Correct - Include page_image file
with open("page_1.png", "rb") as f:
    files = {"page_image": f}
    data = {
        "mapping_context": json.dumps(mapping_context)
    }
    response = requests.post(
        "http://192.168.1.196:8081/api/v1/validate-mappings",
        files=files,
        data=data
    )

# ❌ Wrong - Missing page_image
response = requests.post(
    "http://192.168.1.196:8081/api/v1/validate-mappings",
    data={"mapping_context": json.dumps(mapping_context)}
)
```

### Issue 3: "MISSING_MAPPING_CONTEXT" (400)

**Cause:** `mapping_context` is missing or not valid JSON

**Solution:**
```python
# ✅ Correct - Ensure mapping_context is a JSON string
mapping_context = {
    "case_id": "TS-ABC123-001",
    "page_number": 1,
    "total_pages": 3,
    "columns": [...],
    "rows": [...],
    "images": [...]
}

response = requests.post(
    "http://192.168.1.196:8081/api/v1/validate-mappings",
    files={"page_image": open("page.png", "rb")},
    data={"mapping_context": json.dumps(mapping_context)}  # Must be JSON string
)

# ❌ Wrong - Passing dict directly without json.dumps
response = requests.post(
    "http://192.168.1.196:8081/api/v1/validate-mappings",
    files={"page_image": open("page.png", "rb")},
    data={"mapping_context": mapping_context}  # This won't work!
)
```

### Issue 4: "EMPTY_PAGES" (400)

**Cause:** `pages` array is empty or missing

**Solution:**
```python
# ✅ Correct - Include at least one page
response = requests.post(
    "http://192.168.1.196:8081/api/v1/validate-mappings/batch",
    json={
        "case_id": "TS-ABC123-001",
        "pages": [
            {
                "page_image_path": "page_1.png",
                "mapping_context": {...}
            }
        ]
    }
)

# ❌ Wrong - Empty pages array
response = requests.post(
    "http://192.168.1.196:8081/api/v1/validate-mappings/batch",
    json={
        "case_id": "TS-ABC123-001",
        "pages": []  # Must have at least one page
    }
)
```

### Issue 5: Connection Refused

**Cause:** Server not running or wrong IP/port

**Solution:**
```bash
# Check if server is running
curl http://192.168.1.196:8081/api/v1/health

# Expected response:
# {"status":"healthy","port":8081,...}

# If connection refused, start the server:
cd /home/michael/sandriverfishbot
./venv/bin/python3 api-server.py &
```

---

## Complete Working Examples

### Python Example: Single Page Validation

```python
import requests
import json

BASE_URL = "http://192.168.1.196:8081"

# Prepare mapping context
mapping_context = {
    "case_id": "TS-ABC123-001",
    "page_number": 1,
    "total_pages": 3,
    "columns": [
        {"id": "no", "label": "NO", "description": "Issue number"},
        {"id": "type", "label": "型试", "description": "Trial version"},
        {"id": "item", "label": "项目", "description": "Category"},
        {"id": "problem", "label": "問題點", "description": "Problem description"},
        {"id": "solution", "label": "原因，对策", "description": "Cause and solution"}
    ],
    "rows": [
        {
            "row_id": "r1",
            "values": {
                "no": "1",
                "type": "T0",
                "item": "外观",
                "problem": "披锋问题，产品边缘有毛刺",
                "solution": "调整注塑压力，修整模具分型面"
            }
        }
    ],
    "images": [
        {
            "image_id": "img_001",
            "filename": "case_img001.jpg",
            "anchor": {"row": 23, "col": 8},
            "current_mapping": {
                "row_id": "r1",
                "problem": "披锋问题，产品边缘有毛刺"
            }
        }
    ]
}

# Submit validation job
with open("page_1.png", "rb") as page_img, open("img_001.jpg", "rb") as ext_img:
    files = {
        "page_image": ("page_1.png", page_img, "image/png"),
        "extracted_images[]": ("img_001.jpg", ext_img, "image/jpeg")
    }
    data = {
        "mapping_context": json.dumps(mapping_context, ensure_ascii=False)
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/validate-mappings",
        files=files,
        data=data
    )

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Poll for result
job_id = response.json()["job_id"]
while True:
    status_response = requests.get(f"{BASE_URL}/api/v1/validate-mappings/{job_id}")
    status = status_response.json()
    
    if status["status"] == "completed":
        print(f"Result: {status.get('result', {}).get('summary')}")
        break
    elif status["status"] == "failed":
        print(f"Error: {status.get('error')}")
        break
    
    print(f"Status: {status['status']}, waiting...")
    import time
    time.sleep(2)
```

### Python Example: Batch Validation

```python
import requests
import json

BASE_URL = "http://192.168.1.196:8081"

batch_request = {
    "case_id": "TS-ABC123-001",
    "webhook_url": "https://your-callback.com/webhook",
    "options": {
        "analysis_depth": "detailed",
        "output_language": "zh",
        "include_visual_reasoning": True,
        "include_ocr": True,
        "confidence_threshold": 0.90,
        "max_tokens": 2048
    },
    "pages": [
        {
            "page_image_path": "page_1.png",
            "extracted_images": ["img_001.jpg", "img_002.jpg"],
            "mapping_context": {
                "case_id": "TS-ABC123-001",
                "page_number": 1,
                "total_pages": 3,
                "columns": [...],
                "rows": [...],
                "images": [...]
            }
        },
        {
            "page_image_path": "page_2.png",
            "extracted_images": ["img_003.jpg"],
            "mapping_context": {
                "case_id": "TS-ABC123-001",
                "page_number": 2,
                "total_pages": 3,
                "columns": [...],
                "rows": [...],
                "images": [...]
            }
        }
    ]
}

# Submit batch job
response = requests.post(
    f"{BASE_URL}/api/v1/validate-mappings/batch",
    json=batch_request,  # Important: use json= not data=
    headers={"Content-Type": "application/json"}  # Optional, requests sets this automatically
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

### cURL Example: Single Page

```bash
curl -X POST http://192.168.1.196:8081/api/v1/validate-mappings \
  -F "page_image=@page_1.png" \
  -F "extracted_images[]=@img_001.jpg" \
  -F "extracted_images[]=@img_002.jpg" \
  -F 'mapping_context={
    "case_id": "TS-ABC123-001",
    "page_number": 1,
    "total_pages": 3,
    "columns": [
      {"id": "no", "label": "NO", "description": "Issue number"},
      {"id": "type", "label": "型试", "description": "Trial version"},
      {"id": "item", "label": "项目", "description": "Category"},
      {"id": "problem", "label": "問題點", "description": "Problem description"},
      {"id": "solution", "label": "原因，对策", "description": "Cause and solution"}
    ],
    "rows": [
      {
        "row_id": "r1",
        "values": {
          "no": "1",
          "type": "T0",
          "item": "外观",
          "problem": "披锋问题，产品边缘有毛刺",
          "solution": "调整注塑压力，修整模具分型面"
        }
      }
    ],
    "images": [
      {
        "image_id": "img_001",
        "filename": "case_img001.jpg",
        "anchor": {"row": 23, "col": 8},
        "current_mapping": {
          "row_id": "r1",
          "problem": "披锋问题，产品边缘有毛刺"
        }
      }
    ]
  }'
```

### cURL Example: Batch

```bash
curl -X POST http://192.168.1.196:8081/api/v1/validate-mappings/batch \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "TS-ABC123-001",
    "pages": [
      {
        "page_image_path": "page_1.png",
        "extracted_images": ["img_001.jpg"],
        "mapping_context": {
          "case_id": "TS-ABC123-001",
          "page_number": 1,
          "total_pages": 3,
          "columns": [...],
          "rows": [...],
          "images": [...]
        }
      }
    ]
  }'
```

---

## Response Formats

### Success Response (202 Accepted)

```json
{
  "job_id": "val_abc123def",
  "status": "pending",
  "estimated_duration": "10-30s",
  "status_url": "/api/v1/validate-mappings/val_abc123def"
}
```

### Error Response (4xx/5xx)

```json
{
  "error": {
    "code": "MISSING_PAGE_IMAGE",
    "message": "page_image is required",
    "details": {
      "field": "page_image",
      "received": null
    }
  }
}
```

### Completed Result

```json
{
  "job_id": "val_abc123def",
  "status": "completed",
  "case_id": "TS-ABC123-001",
  "page_number": 1,
  "summary": {
    "total_images": 2,
    "confirmed": 1,
    "corrected": 1,
    "unmatched": 0,
    "ambiguous": 0,
    "average_confidence": 0.935
  },
  "validations": [
    {
      "image_id": "img_001",
      "filename": "case_img001.jpg",
      "current_mapping": {
        "row_id": "r1",
        "problem": "披锋问题，产品边缘有毛刺"
      },
      "validated_mapping": {
        "row_id": "r1",
        "problem": "披锋问题，产品边缘有毛刺"
      },
      "validation_result": {
        "status": "confirmed",
        "confidence": 0.96,
        "reasoning": "Image shows edge burrs on product edge..."
      }
    }
  ]
}
```

---

## Debugging Checklist

- [ ] Server is running (`curl http://192.168.1.196:8081/api/v1/health`)
- [ ] Using correct endpoint (`/api/v1/validate-mappings` or `/api/v1/validate-mappings/batch`)
- [ ] Using correct Content-Type (`multipart/form-data` for single, `application/json` for batch)
- [ ] `mapping_context` is a valid JSON string (not a dict)
- [ ] Required fields are present (`page_image`, `mapping_context`, `pages`)
- [ ] `pages` array is not empty (for batch)
- [ ] `pages` array has maximum 10 items
- [ ] JSON is properly formatted (use a JSON validator)

---

## Server Log Location

If issues persist, check server logs:
```bash
tail -f /tmp/api-server.log
```

Look for entries with:
- `[VALIDATE]` - Single page validation requests
- `[BATCH]` - Batch validation requests
- `[STATUS]` - Status check requests
- `ERROR` - Any errors

---

## Contact

For issues not resolved by this guide, provide:
1. Request endpoint and method
2. Request headers and body (sanitized)
3. Response status code and body
4. Relevant server log entries
