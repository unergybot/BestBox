# Admin Document Management Enhancement

## Problem

BestBox's current Admin UI has a basic single-file upload page with custom OCR processing. It lacks:
- Multi-format document processing with proper structure extraction (tables, images, sections)
- A dashboard to browse, search, and manage indexed knowledge base documents
- Batch upload capability with progress tracking
- Role-based access control for admin operations
- Integration with modern document processing (Docling)

The mold troubleshooting domain relies heavily on Excel case reports with embedded images, which need structured extraction to preserve case-level relationships between defect descriptions, solutions, and visual evidence.

## Architecture

```
+-----------------------------------------------------------+
|                    Admin UI (Next.js :3000)                |
|  +----------+  +----------+  +----------+  +-----------+  |
|  | Document |  |Knowledge |  |  Batch   |  |   User    |  |
|  | Upload   |  |  Base    |  | Upload   |  |   Mgmt    |  |
|  |  Page    |  |Dashboard |  | Monitor  |  |  (RBAC)   |  |
|  +----+-----+  +----+-----+  +----+-----+  +-----+-----+  |
+-------|--------------|--------------|--------------+-------+
        |              |              |              |
   +----v--------------v--------------v--------------v-----+
   |              Agent API (FastAPI :8000)                  |
   |  /admin/documents/*   /admin/kb/*   /admin/users/*     |
   +------+-------------------+---------------------+-------+
          |                   |                     |
   +------v------+    +------v------+        +------v------+
   |Docling Serve|    |   Qdrant    |        | PostgreSQL  |
   |  (:5001)    |    |  (:6333)    |        |  (:5432)    |
   |  - Convert  |    |  - Vectors  |        |  - Users    |
   |  - Chunk    |    |  - Payload  |        |  - Roles    |
   |  - OCR      |    |  - Search   |        |  - Audit    |
   +-------------+    +-------------+        +-------------+
```

### Integration Model

Docling Serve runs as a Docker sidecar container. The Agent API proxies all document conversion requests through internal endpoints, never exposing Docling Serve directly to the frontend.

### Key Design Decisions

1. **Docling Serve as Docker sidecar** (not embedded library or MCP): Keeps document processing decoupled, independently scalable, and avoids dependency conflicts with BestBox's Python environment.
2. **Agent API as orchestrator**: The Agent API coordinates the pipeline (upload -> convert -> extract -> embed -> index) so the frontend only needs to talk to one service.
3. **PostgreSQL for RBAC**: Already available in the Docker Compose stack. Simple users/roles/audit_log schema.
4. **JWT authentication**: Stateless auth tokens with role claims for all admin endpoints.

## Document Processing Pipeline

### Current Flow (Basic)
```
Upload -> Custom OCR (doc_parsing_service.py) -> Raw text chunks -> Qdrant
```

### Enhanced Flow
```
Upload -> Docling Serve conversion -> Domain-specific extraction -> Smart chunking -> Qdrant
```

### Pipeline Steps

#### 1. Upload
Admin uploads file(s) via the UI. The Agent API receives the file and determines processing mode:
- **Sync** (files < 5MB): Immediate Docling conversion, response in seconds
- **Async** (files >= 5MB or batch): Docling async API returns task_id, Agent API polls for completion

#### 2. Docling Conversion
Agent API sends file to Docling Serve `POST /v1/convert/file`:
- Returns structured JSON with table data, embedded images, and text
- Tables are properly extracted preserving row/column structure
- OCR applied to scanned content and embedded images
- Document structure (headings, sections, lists) preserved

Docling configuration per format:
- **Excel (.xlsx)**: Table extraction priority, embedded image export
- **PDF**: OCR engine = EasyOCR, table mode = accurate, image export = embedded
- **Images**: Force OCR, defect analysis prompt
- **DOCX/PPTX**: Standard conversion to Markdown + JSON

#### 3. Domain-Specific Extraction
A `MoldCaseExtractor` processes Docling's structured output:
- Identifies troubleshooting case fields: defect type, mold number, solution, root cause, images
- Maps table columns to structured case records
- Extracts embedded images as separate assets linked to their parent case
- Generates domain-specific metadata: `defect_type`, `mold_id`, `solution_category`, `severity`

For non-mold documents, the standard Docling `HierarchicalChunker` preserves document structure.

#### 4. Chunking Strategy
- **Excel case reports**: Each troubleshooting case = one chunk (preserves case integrity)
- **PDF/DOCX**: Hierarchical chunking respecting section boundaries
- **Images**: Each image = one chunk with VLM-generated description as text

All chunks include rich metadata payload for filtered Qdrant searches.

#### 5. Qdrant Indexing
- Dense embeddings via existing BGE-M3 service (:8004)
- Sparse vectors for hybrid search
- Payload includes: `domain`, `source_file`, `file_type`, `defect_type`, `mold_id`, `upload_date`, `uploaded_by`, `chunk_index`, `has_images`
- Document-level record stored for dashboard queries

## Admin UI Pages

### Page 1: Enhanced Document Upload (`/admin/documents`)

Replaces the current basic upload page.

**Features:**
- Multi-file drag-and-drop upload zone
- File type detection with format icons (Excel, PDF, Image, etc.)
- Processing options panel:
  - OCR engine selection (EasyOCR, Tesseract, RapidOCR)
  - Target collection selector (mold_reference_kb, or other domain KBs)
  - Chunking strategy toggle (case-based for Excel, hierarchical for PDF)
  - Force OCR checkbox
- Per-file progress indicators: uploading -> converting -> extracting -> indexing -> done
- Result summary per file: extracted cases count, images found, chunks created, warnings
- Upload history (recent uploads)

### Page 2: Knowledge Base Dashboard (`/admin/kb`)

New page for managing indexed documents.

**Features:**
- Collection overview cards: document count, total chunks, last updated per collection
- Document browser: paginated, searchable, filterable list
  - Filters: domain, date range, file type, defect category
  - Columns: filename, upload date, chunk count, image count, status
- Document detail view:
  - Extracted text preview (Markdown rendered)
  - Extracted cases with structured data (for Excel files)
  - Image thumbnails with VLM analysis
  - Search test: type a query to see how this document ranks in retrieval
- Bulk actions: select multiple documents to re-index or delete
- Collection management: create/delete collections

### Page 3: User Management (`/admin/users`)

RBAC management page.

**Roles:**
- **Admin**: Full access to all admin features
- **Engineer**: Upload documents, view/search KB, cannot delete or manage users
- **Viewer**: Read-only access to KB dashboard and search

**Features:**
- Login page with JWT token generation
- User list with role assignment
- Create/edit/delete user accounts
- Audit log: who uploaded what, when, deletion history

### Navigation

Admin layout gets a sidebar/tab navigation:
```
Sessions | Documents | Knowledge Base | Users
```

Existing session review page remains as-is.

## Backend API Endpoints

### Document Processing
```
POST   /admin/documents/upload           # Single file upload + process
POST   /admin/documents/batch-upload     # Multi-file upload, returns job_id
GET    /admin/documents/jobs/{job_id}    # Poll batch job status
DELETE /admin/documents/{doc_id}         # Delete document + chunks from Qdrant
```

### Knowledge Base
```
GET    /admin/kb/collections             # List Qdrant collections with stats
GET    /admin/kb/documents               # Paginated document list (filterable)
GET    /admin/kb/documents/{doc_id}      # Document detail with chunks/images
POST   /admin/kb/documents/{doc_id}/reindex  # Re-process and re-index
POST   /admin/kb/search-test             # Test search against KB
DELETE /admin/kb/documents/bulk          # Bulk delete
```

### User Management
```
POST   /admin/auth/login                 # Login -> JWT token
GET    /admin/users                      # List users (admin only)
POST   /admin/users                      # Create user (admin only)
PUT    /admin/users/{user_id}            # Update role (admin only)
DELETE /admin/users/{user_id}            # Delete user (admin only)
GET    /admin/audit-log                  # Paginated audit log
```

### Docling Serve Proxy
```
POST   /admin/docling/convert            # Proxy to Docling /v1/convert/file
GET    /admin/docling/status/{task_id}   # Proxy to Docling /v1/status/poll
GET    /admin/docling/health             # Docling service health check
```

### Auth Middleware
All `/admin/*` endpoints protected by JWT middleware. Token includes user role. Each endpoint checks role permissions:
- Admin: full access
- Engineer: upload, view, search (no delete, no user management)
- Viewer: read-only (KB dashboard, search)

## Implementation Phases

### Phase 1: Docling Integration + Enhanced Upload (Foundation)

**Deliverables:**
- Docker Compose addition for Docling Serve container (CPU image)
- `services/docling_client.py` - Python client wrapping Docling Serve REST API
- Enhanced `/admin/documents/upload` endpoint using Docling for conversion
- `MoldCaseExtractor` processing Docling's structured output
- Enhanced upload page UI with multi-file support and progress tracking
- Admin sidebar navigation

**New files:**
- `docker/docker-compose.docling.yml` - Docling Serve service definition
- `services/docling_client.py` - Docling API client
- `services/mold_case_extractor.py` - Domain-specific case extraction from Docling output

**Modified files:**
- `services/agent_api.py` - New admin document endpoints
- `frontend/copilot-demo/app/admin/layout.tsx` - Sidebar navigation
- `frontend/copilot-demo/app/admin/documents/page.tsx` - Enhanced upload UI

### Phase 2: Knowledge Base Dashboard

**Deliverables:**
- `/admin/kb` page with collection overview
- Document browser with search/filter
- Document detail view with preview and chunk inspection
- Bulk delete operations
- Search test tool

**New files:**
- `frontend/copilot-demo/app/admin/kb/page.tsx` - KB dashboard
- `frontend/copilot-demo/app/admin/kb/[docId]/page.tsx` - Document detail

**Modified files:**
- `services/agent_api.py` - KB management endpoints

### Phase 3: RBAC & User Management

**Deliverables:**
- PostgreSQL schema for users/roles/audit_log
- JWT auth middleware for all admin endpoints
- Login page
- User management page
- Audit logging

**New files:**
- `services/admin_auth.py` - JWT auth, user CRUD, role checks
- `scripts/init_admin_db.py` - Database migration script
- `frontend/copilot-demo/app/admin/login/page.tsx` - Login page
- `frontend/copilot-demo/app/admin/users/page.tsx` - User management

**Modified files:**
- `services/agent_api.py` - Auth middleware on all admin routes
- `docker/docker-compose.yml` - PostgreSQL init script

## Docling Serve Configuration

### Docker Compose Service
```yaml
docling-serve:
  image: quay.io/docling-project/docling-serve
  ports:
    - "5001:5001"
  environment:
    - DOCLING_SERVE_ENABLE_UI=1
  volumes:
    - docling-scratch:/tmp/docling
  restart: unless-stopped
```

For GPU acceleration (optional):
```yaml
docling-serve-gpu:
  image: quay.io/docling-project/docling-serve-cu126
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Default Conversion Options
```python
DOCLING_CONVERT_OPTIONS = {
    "to_formats": ["md", "json"],
    "image_export_mode": "embedded",
    "ocr": True,
    "ocr_engine": "easyocr",
    "ocr_lang": ["ch_sim", "en"],
    "table_mode": "accurate",
    "abort_on_error": False,
}
```

## Data Model

### Qdrant Document Payload Schema
```json
{
  "doc_id": "uuid",
  "source_file": "filename.xlsx",
  "file_type": "xlsx",
  "domain": "mold",
  "collection": "mold_reference_kb",
  "chunk_index": 0,
  "total_chunks": 15,
  "text": "chunk content...",
  "defect_type": "burr",
  "mold_id": "M-2024-001",
  "solution_category": "tooling_adjustment",
  "severity": "medium",
  "has_images": true,
  "image_paths": ["uploads/doc_id/img_001.jpg"],
  "uploaded_by": "user_id",
  "upload_date": "2026-02-06T00:00:00Z",
  "processing_method": "docling",
  "docling_version": "1.11.0"
}
```

### PostgreSQL Schema (Phase 3)
```sql
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'engineer', 'viewer')),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES admin_users(id),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Error Handling

- **Docling Serve unavailable**: Fallback to current custom OCR pipeline (doc_parsing_service.py). UI shows degraded mode warning.
- **Conversion failure**: Per-file error reporting in batch jobs. Failed files don't block others.
- **Large file timeout**: Async mode with configurable timeout (default 5 minutes). Client polls for status.
- **Qdrant indexing failure**: Retry with exponential backoff. Document marked as "conversion complete, indexing failed" for manual retry.

## Testing Strategy

- **Unit tests**: `tests/test_docling_client.py`, `tests/test_mold_case_extractor.py`
- **Integration tests**: `tests/test_admin_document_upload.py` (requires Docling Serve running)
- **Frontend tests**: Component tests for upload UI, KB dashboard
- **Manual testing**: Upload sample Excel case reports and verify extraction quality
