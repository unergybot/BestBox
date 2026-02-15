"""
Admin API endpoints for document management, knowledge base, user management,
and Docling Serve proxy.

This module defines a FastAPI APIRouter that is mounted at /admin in agent_api.py.
All endpoints are protected by JWT authentication with role-based access control.
"""

import base64
import io
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Header,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Upload directory
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls",
    ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp",
}


# ------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str  # admin | engineer | viewer


class UpdateUserRoleRequest(BaseModel):
    role: str


class SearchTestRequest(BaseModel):
    query: str
    collection: str = "mold_reference_kb"
    limit: int = 5


class BulkDeleteRequest(BaseModel):
    doc_ids: List[str]
    collection: str = "mold_reference_kb"


class UploadUrlRequest(BaseModel):
    url: str
    collection: str = "mold_reference_kb"
    domain: str = "mold"
    ocr_engine: str = "easyocr"
    chunking: str = "auto"
    enrich: bool = True
    force: bool = False


class LLMConfigRequest(BaseModel):
    provider: str
    base_url: str
    api_key: Optional[str] = None
    model: str
    parameters: Dict[str, Any] = {
        "temperature": 0.7,
        "max_tokens": 4096,
        "streaming": True,
        "max_retries": 2,
    }


# ------------------------------------------------------------------
# Auth dependency
# ------------------------------------------------------------------

async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Extract and verify JWT or OIDC token from Authorization header.
    Falls back to legacy admin-token header for backward compatibility.
    In dev mode (ADMIN_DEV_MODE=true), auth is bypassed.
    """
    # Dev mode: skip auth entirely for local development
    if os.getenv("ADMIN_DEV_MODE", "").lower() in ("1", "true", "yes"):
        return {"sub": "dev", "username": "dev-admin", "role": "admin"}

    from services.admin_auth import decode_jwt_token, verify_oidc_token

    token = None

    # Try Bearer token first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    # Fallback to legacy admin-token header
    else:
        legacy = request.headers.get("admin-token")
        if legacy:
            expected = os.getenv("ADMIN_TOKEN")
            if expected and legacy == expected:
                return {
                    "sub": "legacy",
                    "username": "admin",
                    "role": "admin",
                }
            raise HTTPException(status_code=401, detail="Invalid admin token")

    if not token:
        raise HTTPException(status_code=401, detail="Authorization required")

    # Try OIDC verification first (Authelia tokens)
    oidc_claims = await verify_oidc_token(token)
    if oidc_claims:
        return oidc_claims

    # Fall back to self-issued JWT
    claims = decode_jwt_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return claims


def require_permission(permission: str):
    """Dependency factory: check the current user has a specific permission."""
    async def _check(user: Dict[str, Any] = Depends(get_current_user)):
        from services.admin_auth import check_permission
        if not check_permission(user.get("role", ""), permission):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: requires '{permission}'",
            )
        return user
    return _check


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_filename(original_name: str) -> str:
    """Sanitize upload filename — allow CJK, alphanumeric, dots, dashes."""
    name = Path(original_name).name
    name = re.sub(r"[^A-Za-z0-9._()\-\u4e00-\u9fff]", "_", name)
    if not name or name in {".", ".."}:
        name = f"upload_{uuid.uuid4().hex[:8]}.bin"
    return name


async def _save_upload(file: UploadFile) -> Path:
    """Save an uploaded file with safety checks. Returns the saved path."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")

    safe_name = _safe_filename(file.filename)
    timestamped = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_name}"
    saved_path = UPLOAD_DIR / timestamped
    saved_path.parent.mkdir(parents=True, exist_ok=True)
    saved_path.write_bytes(content)

    return saved_path


async def _download_url(url: str) -> tuple[Path, str]:
    """Download a file from *url* into UPLOAD_DIR with safety checks.

    Returns ``(saved_path, original_filename)``.
    Raises ``HTTPException(400)`` for invalid scheme, extension, or size.
    """
    from urllib.parse import urlparse

    import httpx

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported URL scheme: {parsed.scheme!r}. Only http/https allowed.",
        )

    # Extract filename from the URL path
    url_path = parsed.path.rstrip("/")
    original_filename = Path(url_path).name if url_path else ""
    if not original_filename:
        raise HTTPException(status_code=400, detail="Cannot determine filename from URL")

    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    safe_name = _safe_filename(original_filename)
    timestamped = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_name}"
    saved_path = UPLOAD_DIR / timestamped
    saved_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Download failed with HTTP {resp.status_code}",
                    )

                # Pre-check Content-Length header if available
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail="Remote file exceeds 50 MB limit",
                    )

                total = 0
                with open(saved_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        total += len(chunk)
                        if total > MAX_FILE_SIZE:
                            f.close()
                            saved_path.unlink(missing_ok=True)
                            raise HTTPException(
                                status_code=400,
                                detail="Download exceeded 50 MB limit",
                            )
                        f.write(chunk)

        if total == 0:
            saved_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Downloaded file is empty")

    except HTTPException:
        raise
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Download error: {exc}",
        ) from exc

    return saved_path, original_filename


def _extract_layout_stats(markdown: str) -> Dict[str, int]:
    """Extract layout statistics from GLM-OCR markdown output.

    GLM-OCR uses specific formats:
    - Images: ![](page=N,bbox=[x1,y1,x2,y2])
    - Tables: HTML <table> tags or markdown pipes
    - Headers: Standard markdown ## format
    """
    # Tables: check both HTML and markdown formats
    html_tables = len(re.findall(r"<table\b", markdown, flags=re.IGNORECASE))
    md_tables = len(re.findall(r"^\|.+\|$", markdown, flags=re.MULTILINE))
    tables = html_tables + md_tables

    # Images: GLM-SDK uses ![](page=N,bbox=[...]) format
    images = len(re.findall(r"!\[\]\(page=\d+,bbox=", markdown))

    # Headers: Standard markdown format
    headers = len(re.findall(r"^#{1,6}\s+.+", markdown, flags=re.MULTILINE))

    return {
        "tables": tables,
        "images": images,
        "headers": headers,
    }


def _is_glm_image_element(elem: Dict[str, Any]) -> bool:
    """Return True for image/chart elements only (precision-first)."""
    elem_type = str(elem.get("type") or "").lower()
    raw_label = elem.get("label")

    # Explicit type signal.
    if elem_type in {"image", "chart"}:
        return True

    # Normalize PP-DocLayoutV3 labels (string or numeric id).
    label_id_map = {3: "chart", 14: "image"}
    label = ""
    if isinstance(raw_label, (int, float)):
        label = label_id_map.get(int(raw_label), "")
    elif isinstance(raw_label, str):
        label = raw_label.strip().lower()
        if label.isdigit():
            label = label_id_map.get(int(label), label)

    if label in {"chart", "image"}:
        return True

    reject_labels = {
        "header",
        "footer",
        "figure_title",
        "doc_title",
        "paragraph_title",
        "text",
        "content",
        "abstract",
        "reference_content",
        "table",  # Tables have their own extraction path, don't extract as images
    }
    if label in reject_labels:
        return False

    # Fallback: only accept if bbox exists and no conflicting label.
    return "bbox_2d" in elem


def _normalize_bbox(bbox: Any) -> Optional[List[float]]:
    if bbox is None:
        return None
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        except Exception:
            return None
    if isinstance(bbox, dict):
        keys = ["x1", "y1", "x2", "y2"]
        if all(k in bbox for k in keys):
            try:
                return [float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"])]
            except Exception:
                return None
    return None


async def _extract_images_from_pdf(
    pdf_path: Path,
    json_result: List[List[Dict[str, Any]]],
    doc_id: str,
    collection: str,
    base_dir: Optional[Path] = None,
    dpi: int = 200,
) -> Dict[str, Dict[str, Any]]:
    """Extract image regions from *pdf_path* using GLM-OCR bbox data.

    Stores PNG crops under: data/uploads/images/{collection}/{doc_id}/p{page}_img{index}.png

    Returns a manifest keyed by image_id (e.g. 'p0_img0').
    """
    if fitz is None:
        raise RuntimeError("pymupdf_not_installed")

    # Basic path safety: keep within IMAGE_DIR
    safe_collection = re.sub(r"[^A-Za-z0-9._\-]", "_", collection)
    safe_doc_id = re.sub(r"[^A-Za-z0-9._\-]", "_", doc_id)

    root_dir = base_dir or IMAGE_DIR
    image_dir = root_dir / safe_collection / safe_doc_id
    image_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Dict[str, Any]] = {}
    bbox_to_id: Dict[tuple[int, tuple[int, int, int, int]], str] = {}
    rejected_count = 0

    pdf = fitz.open(str(pdf_path))
    try:
        for page_idx, page_elements in enumerate(json_result or []):
            if page_idx >= len(pdf):
                continue

            page = pdf[page_idx]
            page_rect = page.rect
            img_idx = 0

            for elem in page_elements or []:
                if not _is_glm_image_element(elem):
                    if elem.get("bbox_2d") or elem.get("bbox"):
                        rejected_count += 1
                    continue
                # GLM-SDK uses "bbox_2d" not "bbox"
                bbox = _normalize_bbox(elem.get("bbox_2d") or elem.get("bbox"))
                if not bbox:
                    continue

                x1, y1, x2, y2 = bbox
                # Normalize ordering and clamp to page bounds
                x0 = max(min(x1, x2), page_rect.x0)
                y0 = max(min(y1, y2), page_rect.y0)
                x1c = min(max(x1, x2), page_rect.x1)
                y1c = min(max(y1, y2), page_rect.y1)
                if x1c - x0 < 1 or y1c - y0 < 1:
                    continue

                rect = fitz.Rect(x0, y0, x1c, y1c)
                image_id = f"p{page_idx}_img{img_idx}"
                out_path = image_dir / f"{image_id}.png"

                try:
                    pix = page.get_pixmap(clip=rect, dpi=dpi)
                    pix.save(str(out_path))
                except Exception as exc:
                    logger.warning(
                        f"Failed to crop image {image_id} from {pdf_path.name}: {exc}"
                    )
                    continue

                bbox_key = (page_idx, tuple(int(round(v)) for v in bbox))
                bbox_to_id[bbox_key] = image_id
                manifest[image_id] = {
                    "image_id": image_id,
                    "page": page_idx,
                    "bbox": bbox,
                    "path": str(out_path),
                }
                img_idx += 1

        if manifest:
            heights = [img["bbox"][3] - img["bbox"][1] for img in manifest.values()]
            avg_height = sum(heights) / len(heights)
        else:
            avg_height = 0.0
        logger.info(
            "Image extraction stats for %s: detected=%s images, avg_height=%.0fpt, rejected_text_blocks=%s",
            pdf_path.name,
            len(manifest),
            avg_height,
            rejected_count,
        )

        # Persist manifest to disk for debugging/cleanup
        try:
            (image_dir / "metadata.json").write_text(
                json.dumps({"images": manifest}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        # Store lookup mapping (used by placeholder replacement)
        manifest["__bbox_to_id__"] = {  # type: ignore[assignment]
            "data": {
                f"{p}:{b[0]},{b[1]},{b[2]},{b[3]}": image_id
                for (p, b), image_id in bbox_to_id.items()
            }
        }
        return manifest
    finally:
        pdf.close()


def _replace_image_placeholders(markdown: str, manifest: Dict[str, Dict[str, Any]]) -> str:
    """Replace GLM-OCR bbox placeholders with image IDs.

    Converts: ![](page=N,bbox=[x1, y1, x2, y2])
    Into:     <!-- image:pN_imgX -->

    If no matching image is found in the manifest, the placeholder is left unchanged.
    """
    if not markdown:
        return markdown

    bbox_map: Dict[str, str] = {}
    bbox_blob = manifest.get("__bbox_to_id__", {}).get("data") if isinstance(manifest.get("__bbox_to_id__"), dict) else None
    if isinstance(bbox_blob, dict):
        bbox_map = {str(k): str(v) for k, v in bbox_blob.items()}

    pattern = re.compile(
        r"!\[\]\(page=(\d+),bbox=\[\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*\]\)"
    )

    def _key(page: int, x1: float, y1: float, x2: float, y2: float) -> str:
        vals = [int(round(v)) for v in (x1, y1, x2, y2)]
        return f"{page}:{vals[0]},{vals[1]},{vals[2]},{vals[3]}"

    def replace_match(m: re.Match[str]) -> str:
        page = int(m.group(1))
        x1 = float(m.group(2))
        y1 = float(m.group(3))
        x2 = float(m.group(4))
        y2 = float(m.group(5))
        image_id = bbox_map.get(_key(page, x1, y1, x2, y2))
        if image_id:
            return f"<!-- image:{image_id} -->"
        return m.group(0)

    return pattern.sub(replace_match, markdown)


async def _process_with_glm_ocr(
    pdf_path: Path,
    domain: str,
    *,
    doc_id: Optional[str] = None,
    collection: Optional[str] = None,
) -> tuple[Dict[str, Any], Dict[str, int], float]:
    import httpx
    import subprocess
    import uuid

    start_time = time.monotonic()
    glm_url = os.getenv("GLM_SDK_URL", "http://localhost:5002").rstrip("/")

    # Copy PDF to shared volume for GLM-SDK container access
    unique_filename = f"{uuid.uuid4().hex[:8]}_{pdf_path.name}"
    container_path = f"/app/shared/{unique_filename}"

    try:
        # Copy file to GLM-SDK container's shared volume
        subprocess.run(
            ["docker", "cp", str(pdf_path), f"bestbox-glm-sdk:{container_path}"],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to copy PDF to GLM-SDK container: {e.stderr}")
        raise RuntimeError("glm_sdk_file_copy_failed") from e

    # Configurable timeouts for large PDFs
    glm_timeout = int(os.getenv("GLM_OCR_TIMEOUT", "300"))
    glm_connect_timeout = int(os.getenv("GLM_OCR_CONNECT_TIMEOUT", "10"))

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(glm_timeout, connect=glm_connect_timeout)
        ) as client:
            try:
                response = await client.post(
                    f"{glm_url}/glmocr/parse",
                    json={"images": [container_path]},
                )
            except httpx.ConnectError as exc:
                raise RuntimeError("glm_ocr_unavailable") from exc
    finally:
        # Cleanup: remove temporary file from container
        try:
            subprocess.run(
                ["docker", "exec", "bestbox-glm-sdk", "rm", "-f", container_path],
                check=False,  # Don't fail if cleanup fails
                capture_output=True
            )
        except Exception:
            pass  # Ignore cleanup errors

    if response.status_code != 200:
        body_text = response.text or ""
        if response.status_code >= 500 and "out of memory" in body_text.lower():
            raise HTTPException(
                status_code=500,
                detail=(
                    "GPU memory exceeded. Please split the PDF into smaller files "
                    "(max 50 pages recommended)."
                ),
            )
        raise RuntimeError(
            f"glm_ocr_failed_{response.status_code}: {body_text[:200]}"
        )

    result = response.json()
    markdown = result.get("markdown_result", "")
    json_result = result.get("json_result", [])
    if not markdown or len(markdown.strip()) < 10:
        logger.error(
            f"GLM-OCR returned empty/invalid markdown for {pdf_path.name}. "
            f"Response keys: {list(result.keys())}, markdown length: {len(markdown)}"
        )
        raise RuntimeError("glm_ocr_empty_result")

    # Optional: extract image crops + replace placeholders
    if collection and doc_id and json_result:
        try:
            manifest = await _extract_images_from_pdf(
                pdf_path=pdf_path,
                json_result=json_result,
                doc_id=doc_id,
                collection=collection,
            )
            markdown = _replace_image_placeholders(markdown, manifest)
        except Exception as exc:
            logger.warning(f"GLM image extraction skipped: {exc}")

    layout_stats = _extract_layout_stats(markdown)
    processing_time = time.monotonic() - start_time
    
    logger.info(
        f"GLM-OCR extracted {len(markdown)} chars from {pdf_path.name}: "
        f"{layout_stats['tables']} tables, {layout_stats['images']} images, "
        f"{layout_stats['headers']} headers"
    )

    docling_result = {
        "md": markdown,
        "document": {"content": [{"text": markdown}]},
        "pictures": [],
        "metadata": {
            "domain": domain,
            "source": str(pdf_path),
            "ocr_engine": "glm-ocr",
            "json_result": json_result,
        },
    }

    return docling_result, layout_stats, processing_time


async def _process_with_quality_gate(
    pdf_path: Path,
    domain: str,
) -> Dict[str, Any]:
    from services.rag_pipeline.mold_document_ingester import MoldDocumentIngester

    ingester = MoldDocumentIngester()
    try:
        parse_result = await ingester.ingest_document(
            doc_path=pdf_path,
            domain=domain,
            run_ocr=True,
        )
        if not parse_result:
            raise RuntimeError("GPU OCR service returned no result")

        docling_result = {
            "md": parse_result.get("text", ""),
            "document": {
                "content": [{"text": parse_result.get("raw_text", "")}]
            },
            "pictures": [],
            "metadata": parse_result.get("metadata", {}),
        }
        logger.info(
            "PDF processed via GPU OCR: %s images, %s OCR results",
            parse_result.get("image_count", 0),
            len(parse_result.get("ocr_results", [])),
        )
        return docling_result
    finally:
        await ingester.close()


def _get_db_pool(request: Request):
    """Retrieve the asyncpg pool from app state or agent_api global."""
    # First try app state
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        # Try legacy _admin_db_pool attribute
        pool = getattr(request.app, "_admin_db_pool", None)
    return pool


# ------------------------------------------------------------------
# Auth endpoints
# ------------------------------------------------------------------

@router.post("/auth/login")
async def admin_login(body: LoginRequest, request: Request):
    """Authenticate and return a JWT token."""
    from services.admin_auth import authenticate_user, log_audit

    pool = _get_db_pool(request)
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    result = await authenticate_user(pool, body.username, body.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await log_audit(
        pool,
        result["user"]["id"],
        "login",
        resource_type="auth",
    )

    return result


@router.post("/auth/oidc/callback")
async def oidc_callback(request: Request):
    """Handle OIDC authorization code callback from Authelia.

    Exchanges the authorization code for tokens and returns user info.
    """
    from services.admin_auth import (
        get_oidc_metadata,
        OIDC_CLIENT_ID,
        OIDC_CLIENT_SECRET,
    )
    import aiohttp

    body = await request.json()
    code = body.get("code")
    locale = body.get("locale", "en")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    metadata = await get_oidc_metadata()
    token_endpoint = metadata.get("token_endpoint")
    userinfo_endpoint = metadata.get("userinfo_endpoint")

    if not token_endpoint or not userinfo_endpoint:
        raise HTTPException(status_code=500, detail="OIDC endpoints not available")

    try:
        redirect_uri = f"http://localhost:3000/{locale}/admin/callback"
        async with aiohttp.ClientSession() as session:
            # Exchange authorization code for tokens
            async with session.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "client_id": OIDC_CLIENT_ID,
                    "client_secret": OIDC_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    detail = await resp.text()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Token exchange failed: {detail}",
                    )
                token_data = await resp.json()

            access_token = token_data.get("access_token")
            id_token = token_data.get("id_token")

            if not access_token:
                raise HTTPException(status_code=400, detail="No access token received")

            # Fetch user info
            async with session.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=400, detail="Userinfo fetch failed")
                userinfo = await resp.json()

        username = userinfo.get("preferred_username") or userinfo.get("sub")
        groups = userinfo.get("groups", [])

        role = "viewer"
        if "admin" in groups:
            role = "admin"
        elif "engineer" in groups:
            role = "engineer"

        return {
            "access_token": access_token,
            "id_token": id_token,
            "user": {
                "username": username,
                "role": role,
                "groups": groups,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OIDC callback error: {e}")
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")


# ------------------------------------------------------------------
# Document Processing endpoints
# ------------------------------------------------------------------

@router.post("/documents/upload")
async def admin_upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection: str = Query("mold_reference_kb", description="Target Qdrant collection"),
    domain: str = Query("mold", description="Domain classification"),
    ocr_engine: str = Query("easyocr", description="OCR engine: easyocr, tesseract, rapidocr, glm-ocr"),
    chunking: str = Query("auto", description="Chunking strategy: auto, case, hierarchical"),
    force_ocr: bool = Query(False, description="Force OCR even on text-rich documents"),
    user: Dict = Depends(require_permission("upload")),
):
    """
    Upload and process a single document through the Docling pipeline.

    Flow: upload → Docling conversion → domain extraction → chunking → Qdrant indexing
    """
    from services.admin_auth import log_audit

    saved_path = await _save_upload(file)
    ext = saved_path.suffix.lower()
    pool = _get_db_pool(request)

    # One doc_id for the entire ingestion flow (indexing + image storage)
    doc_id = str(uuid.uuid4())

    layout_stats: Optional[Dict[str, int]] = None
    processing_time: Optional[float] = None

    try:
        # Step 1: Document conversion with GPU OCR for PDFs
        # PDFs with images use GPU-accelerated pipeline: P100 (classical OCR) + RTX 3080 (GLM-OCR for quality fallback)
        # Other formats use Docling Serve
        
        if ext == ".pdf":
            if ocr_engine == "glm-ocr":
                try:
                    docling_result, layout_stats, processing_time = await _process_with_glm_ocr(
                        saved_path,
                        domain,
                        doc_id=doc_id,
                        collection=collection,
                    )
                    processing_method = "glm-ocr"
                    logger.info(
                        f"GLM-OCR processed {file.filename}: "
                        f"{layout_stats['tables']} tables, {layout_stats['images']} images, "
                        f"{layout_stats['headers']} headers, {processing_time:.1f}s"
                    )
                except RuntimeError as exc:
                    logger.warning(f"GLM-OCR failed, falling back to quality gate: {exc}")
                    docling_result = await _process_with_quality_gate(saved_path, domain)
                    processing_method = "fallback-quality-gate"
            else:
                docling_result = await _process_with_quality_gate(saved_path, domain)
                processing_method = "gpu_ocr"
        else:
            # Non-PDF files: use Docling Serve (DOCX, PPTX, images, etc.)
            from services.docling_client import DoclingClient

            client = DoclingClient()
            options = client.options_for_format(ext)
            if force_ocr:
                options["force_ocr"] = True
            if ocr_engine in {"tesseract", "rapidocr"}:
                options["ocr_engine"] = ocr_engine
            elif ocr_engine == "glm-ocr":
                logger.warning(
                    f"GLM-OCR selected for {ext} file ({file.filename}), "
                    "but GLM-OCR only supports PDFs. Falling back to EasyOCR."
                )

            docling_result = await client.convert_file(str(saved_path), options)
            processing_method = "docling"

        # Step 2: Domain-specific extraction
        chunks: List[Dict[str, Any]] = []
        if domain == "mold" and ext in (".xlsx", ".xls"):
            from services.mold_case_extractor import MoldCaseExtractor
            extractor = MoldCaseExtractor()
            chunks = extractor.extract(
                docling_result,
                source_file=file.filename or saved_path.name,
                uploaded_by=user.get("username", ""),
            )
        else:
            # Generic hierarchical chunking with image extraction
            images = _extract_and_save_images(docling_result, doc_id=doc_id)
            chunks = _hierarchical_chunk(
                docling_result,
                source_file=file.filename or saved_path.name,
                domain=domain,
                uploaded_by=user.get("username", ""),
                images=images,
                doc_id=doc_id,
                processing_method=processing_method,
            )
        
        # Validate chunks were created
        if not chunks:
            logger.error(
                f"Chunking failed for {file.filename}: no chunks extracted. "
                f"Processing method: {processing_method}, domain: {domain}, ext: {ext}"
            )
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Failed to extract text chunks from {file.filename}. "
                    "The document may be empty, corrupted, or in an unsupported format."
                ),
            )
        
        logger.info(f"Extracted {len(chunks)} chunks from {file.filename}")

        # Step 3: Embed and index into Qdrant
        indexed_count = await _index_chunks(chunks, collection)
        if indexed_count == 0:
            logger.error(
                f"Indexing returned 0 for {file.filename} ({len(chunks)} chunks). "
                "Embeddings or Qdrant likely down."
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Indexing failed for {len(chunks)} chunks. "
                    "Please verify embeddings service (port 8004) and Qdrant (port 6333) "
                    "are running, then retry the upload."
                ),
            )
        
        logger.info(
            f"Successfully indexed {indexed_count} chunks from {file.filename} "
            f"to collection '{collection}'"
        )

        # Audit log
        if pool:
            await log_audit(
                pool,
                user.get("sub"),
                "upload_document",
                resource_type="document",
                resource_id=file.filename or "",
                details={
                    "collection": collection,
                    "domain": domain,
                    "chunks": len(chunks),
                    "indexed": indexed_count,
                    "file_type": ext,
                },
            )

        response_data: Dict[str, Any] = {
            "status": "success",
            "filename": file.filename,
            "file_type": ext.lstrip("."),
            "chunks_extracted": len(chunks),
            "chunks_indexed": indexed_count,
            "collection": collection,
            "domain": domain,
            "processing_method": processing_method,
        }

        if ocr_engine == "glm-ocr" and layout_stats:
            response_data["layout_detected"] = layout_stats
            if processing_time is not None:
                response_data["processing_time"] = processing_time

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)

        # Try fallback to legacy OCR pipeline
        try:
            return await _fallback_upload(saved_path, file.filename or "", collection, domain)
        except Exception as fallback_err:
            logger.error(f"Fallback upload also failed: {fallback_err}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {e}")


@router.post("/documents/batch-upload")
async def admin_batch_upload(
    request: Request,
    files: List[UploadFile] = File(...),
    collection: str = Query("mold_reference_kb"),
    domain: str = Query("mold"),
    user: Dict = Depends(require_permission("upload")),
):
    """
    Batch upload multiple documents. Returns a job_id for status polling.
    """
    import asyncio
    from services.admin_auth import log_audit

    job_id = str(uuid.uuid4())
    pool = _get_db_pool(request)

    # Save all files first
    saved_files: List[Dict[str, Any]] = []
    for f in files:
        try:
            path = await _save_upload(f)
            saved_files.append({
                "filename": f.filename or path.name,
                "path": str(path),
                "status": "pending",
            })
        except HTTPException as e:
            saved_files.append({
                "filename": f.filename or "unknown",
                "path": "",
                "status": "error",
                "error": e.detail,
            })

    # Store job state in memory (for polling)
    _batch_jobs[job_id] = {
        "id": job_id,
        "status": "processing",
        "total": len(saved_files),
        "completed": 0,
        "failed": 0,
        "files": saved_files,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Process files in background
    asyncio.create_task(
        _process_batch(job_id, saved_files, collection, domain, user, pool)
    )

    if pool:
        await log_audit(
            pool,
            user.get("sub"),
            "batch_upload",
            resource_type="batch",
            resource_id=job_id,
            details={"file_count": len(saved_files), "collection": collection},
        )

    return {"job_id": job_id, "files": len(saved_files), "status": "processing"}


# In-memory batch job store (simple — production would use Redis)
_batch_jobs: Dict[str, Dict[str, Any]] = {}


@router.post("/documents/upload-url")
async def admin_upload_url(
    body: UploadUrlRequest,
    request: Request,
    user: Dict = Depends(require_permission("upload")),
):
    """
    Download a document from a URL and process it through the Docling pipeline.

    Returns a job_id for status polling via GET /admin/documents/jobs/{job_id}.
    """
    import asyncio
    from services.admin_auth import log_audit

    pool = _get_db_pool(request)

    # Duplicate check: look for points with matching source_url in Qdrant
    if not body.force:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            qdrant = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
            )
            points, _ = qdrant.scroll(
                collection_name=body.collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="source_url",
                            match=MatchValue(value=body.url),
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False,
            )
            if points:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": "URL already indexed. Use force=true to re-import."
                    },
                )
        except Exception:
            # Collection may not exist yet — that's fine, no duplicates
            pass

    # Download the file
    saved_path, filename = await _download_url(body.url)

    # Create a job for status polling
    job_id = str(uuid.uuid4())
    _batch_jobs[job_id] = {
        "id": job_id,
        "status": "processing",
        "stage": "downloading",
        "url": body.url,
        "filename": filename,
        "total_chunks": 0,
        "enriched_chunks": 0,
        "enrichment_progress": "",
        "completed": 0,
        "failed": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Dispatch background processing
    asyncio.create_task(
        _process_url_job(job_id, saved_path, filename, body, user, pool)
    )

    # Audit log
    if pool:
        await log_audit(
            pool,
            user.get("sub"),
            "upload_url",
            resource_type="document",
            resource_id=job_id,
            details={
                "url": body.url,
                "collection": body.collection,
                "domain": body.domain,
                "filename": filename,
            },
        )

    return {"job_id": job_id, "filename": filename, "status": "processing"}


@router.get("/documents/jobs/{job_id}")
async def admin_get_job_status(
    job_id: str,
    user: Dict = Depends(require_permission("view")),
):
    """Poll batch upload job status."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/documents/{doc_id}")
async def admin_delete_document(
    doc_id: str,
    request: Request,
    collection: str = Query("mold_reference_kb"),
    user: Dict = Depends(require_permission("delete")),
):
    """Delete a document and all its chunks from Qdrant."""
    from services.admin_auth import log_audit

    pool = _get_db_pool(request)
    deleted = await _delete_from_qdrant(doc_id, collection)

    if pool:
        await log_audit(
            pool,
            user.get("sub"),
            "delete_document",
            resource_type="document",
            resource_id=doc_id,
            details={"collection": collection, "chunks_deleted": deleted},
        )

    return {"status": "deleted", "doc_id": doc_id, "chunks_deleted": deleted}


# ------------------------------------------------------------------
# Knowledge Base endpoints
# ------------------------------------------------------------------

@router.get("/kb/collections")
async def admin_list_collections(
    user: Dict = Depends(require_permission("view")),
):
    """List Qdrant collections with stats."""
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
        collections = client.get_collections().collections
        result = []
        for col in collections:
            info = client.get_collection(col.name)
            result.append({
                "name": col.name,
                "points_count": info.points_count,
                "vectors_count": getattr(info, 'vectors_count', info.points_count),
                "status": info.status.value if info.status else "unknown",
            })
        return result
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")


@router.get("/kb/documents")
async def admin_list_documents(
    collection: str = Query("mold_reference_kb"),
    domain: Optional[str] = None,
    file_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Dict = Depends(require_permission("view")),
):
    """Paginated, filterable list of indexed documents."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )

        # Build filter conditions
        conditions = []
        if domain:
            conditions.append(
                FieldCondition(key="domain", match=MatchValue(value=domain))
            )
        if file_type:
            conditions.append(
                FieldCondition(key="file_type", match=MatchValue(value=file_type))
            )

        scroll_filter = Filter(must=conditions) if conditions else None

        # Scroll through ALL points to group by document.
        # We need to see every chunk to build accurate document-level summaries.
        all_points = []
        page_offset = None
        while True:
            points, page_offset = client.scroll(
                collection_name=collection,
                scroll_filter=scroll_filter,
                limit=100,
                offset=page_offset,
                with_payload=True,
                with_vectors=False,
            )
            all_points.extend(points)
            if page_offset is None:
                break

        # Group by doc_id (preferred) or source filename (fallback for
        # points indexed without doc_id).
        docs: Dict[str, Dict[str, Any]] = {}
        for point in all_points:
            payload = point.payload or {}
            doc_id = payload.get("doc_id") or payload.get("source") or str(point.id)
            if doc_id not in docs:
                # Derive file_type from source filename if not stored
                source = payload.get("source_file") or payload.get("source", "")
                ft = payload.get("file_type", "")
                if not ft and "." in source:
                    ft = source.rsplit(".", 1)[-1].lower()
                # Derive upload_date from timestamp if not stored
                upload_date = payload.get("upload_date", "")
                if not upload_date and payload.get("timestamp"):
                    from datetime import datetime, timezone
                    try:
                        upload_date = datetime.fromtimestamp(
                            payload["timestamp"], tz=timezone.utc
                        ).isoformat()
                    except (ValueError, OSError):
                        pass
                docs[doc_id] = {
                    "doc_id": doc_id,
                    "source_file": source,
                    "file_type": ft,
                    "domain": payload.get("domain", ""),
                    "upload_date": upload_date,
                    "uploaded_by": payload.get("uploaded_by", ""),
                    "chunk_count": 0,
                    "has_images": payload.get("has_images", False),
                }
            docs[doc_id]["chunk_count"] += 1

        # Apply pagination at document level
        doc_list = list(docs.values())
        paginated = doc_list[offset : offset + limit]

        return {
            "documents": paginated,
            "total": len(doc_list),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")


@router.get("/kb/documents/{doc_id}")
async def admin_get_document(
    doc_id: str,
    collection: str = Query("mold_reference_kb"),
    user: Dict = Depends(require_permission("view")),
):
    """Document detail: all chunks, images, metadata for a given doc_id."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )

        # Try doc_id field first, fall back to source field for points
        # that were indexed without doc_id.
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=500,
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            points, _ = client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=doc_id))]
                ),
                limit=500,
                with_payload=True,
                with_vectors=False,
            )

        if not points:
            raise HTTPException(status_code=404, detail="Document not found")

        chunks = []
        metadata = {}
        for point in points:
            payload = point.payload or {}
            if not metadata:
                source = payload.get("source_file") or payload.get("source", "")
                ft = payload.get("file_type", "")
                if not ft and "." in source:
                    ft = source.rsplit(".", 1)[-1].lower()
                upload_date = payload.get("upload_date", "")
                if not upload_date and payload.get("timestamp"):
                    from datetime import datetime, timezone
                    try:
                        upload_date = datetime.fromtimestamp(
                            payload["timestamp"], tz=timezone.utc
                        ).isoformat()
                    except (ValueError, OSError):
                        pass
                metadata = {
                    "doc_id": doc_id,
                    "source_file": source,
                    "file_type": ft,
                    "domain": payload.get("domain", ""),
                    "upload_date": upload_date,
                    "uploaded_by": payload.get("uploaded_by", ""),
                    "processing_method": payload.get("processing_method", ""),
                    "source_url": payload.get("source_url", ""),
                }
            chunks.append({
                "chunk_index": payload.get("chunk_index", 0),
                "text": payload.get("text", ""),
                "defect_type": payload.get("defect_type", ""),
                "mold_id": payload.get("mold_id", ""),
                "severity": payload.get("severity", ""),
                "has_images": payload.get("has_images", False),
                "image_ids": payload.get("image_ids", []),
                "image_count": payload.get("image_count", 0),
                "image_paths": payload.get("image_paths", []),
                "chunk_type": payload.get("chunk_type", "original"),
                "root_cause_category": payload.get("root_cause_category", ""),
            })

        chunks.sort(key=lambda c: c.get("chunk_index", 0))

        return {
            **metadata,
            "total_chunks": len(chunks),
            "chunks": chunks,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")


@router.post("/kb/documents/{doc_id}/reindex")
async def admin_reindex_document(
    doc_id: str,
    request: Request,
    collection: str = Query("mold_reference_kb"),
    user: Dict = Depends(require_permission("reindex")),
):
    """Re-process and re-index a document."""
    from services.admin_auth import log_audit

    pool = _get_db_pool(request)

    # Find the original file from Qdrant metadata
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            raise HTTPException(status_code=404, detail="Document not found in index")

        source_file = points[0].payload.get("source_file", "")
        domain = points[0].payload.get("domain", "mold")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant error: {e}")

    # Delete existing chunks
    await _delete_from_qdrant(doc_id, collection)

    if pool:
        await log_audit(
            pool,
            user.get("sub"),
            "reindex_document",
            resource_type="document",
            resource_id=doc_id,
            details={"collection": collection, "source_file": source_file},
        )

    return {
        "status": "reindex_queued",
        "doc_id": doc_id,
        "source_file": source_file,
        "note": "Original file would need to be re-uploaded for full re-processing",
    }


@router.post("/kb/search-test")
async def admin_search_test(
    body: SearchTestRequest,
    user: Dict = Depends(require_permission("search")),
):
    """Test search against the knowledge base — returns ranked results."""
    try:
        from qdrant_client import QdrantClient
        import httpx

        embeddings_url = os.getenv(
            "EMBEDDINGS_URL",
            os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
        )

        # Get query embedding
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resp = await http_client.post(
                f"{embeddings_url}/embed",
                json={"inputs": [body.query]},  # Fixed: API expects 'inputs' not 'texts'
            )
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
            if not embeddings:
                raise HTTPException(status_code=500, detail="Embedding service returned no vectors")
            query_vector = embeddings[0]

        qdrant = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )

        results = qdrant.search(
            collection_name=body.collection,
            query_vector=query_vector,
            limit=body.limit,
            with_payload=True,
        )

        return {
            "query": body.query,
            "collection": body.collection,
            "results": [
                {
                    "score": hit.score,
                    "doc_id": hit.payload.get("doc_id") or hit.payload.get("source", ""),
                    "source_file": hit.payload.get("source_file") or hit.payload.get("source", ""),
                    "text": hit.payload.get("text", "")[:500],
                    "defect_type": hit.payload.get("defect_type", ""),
                    "mold_id": hit.payload.get("mold_id", ""),
                    "domain": hit.payload.get("domain", ""),
                }
                for hit in results
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search test failed: {e}")
        raise HTTPException(status_code=503, detail=f"Search failed: {e}")


@router.delete("/kb/documents/bulk")
async def admin_bulk_delete(
    body: BulkDeleteRequest,
    request: Request,
    user: Dict = Depends(require_permission("delete")),
):
    """Bulk delete multiple documents from the knowledge base."""
    from services.admin_auth import log_audit

    pool = _get_db_pool(request)
    total_deleted = 0

    for doc_id in body.doc_ids:
        deleted = await _delete_from_qdrant(doc_id, body.collection)
        total_deleted += deleted

    if pool:
        await log_audit(
            pool,
            user.get("sub"),
            "bulk_delete",
            resource_type="documents",
            details={
                "collection": body.collection,
                "doc_ids": body.doc_ids,
                "total_deleted": total_deleted,
            },
        )

    return {
        "status": "deleted",
        "doc_ids": body.doc_ids,
        "total_chunks_deleted": total_deleted,
    }


# ------------------------------------------------------------------
# User Management endpoints
# ------------------------------------------------------------------

@router.get("/users")
async def admin_list_users(
    request: Request,
    user: Dict = Depends(require_permission("manage_users")),
):
    """List all admin users (admin only)."""
    from services.admin_auth import list_users

    pool = _get_db_pool(request)
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")
    return await list_users(pool)


@router.post("/users")
async def admin_create_user(
    body: CreateUserRequest,
    request: Request,
    user: Dict = Depends(require_permission("manage_users")),
):
    """Create a new user (admin only)."""
    from services.admin_auth import create_user, log_audit

    pool = _get_db_pool(request)
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        new_user = await create_user(pool, body.username, body.password, body.role)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    await log_audit(
        pool,
        user.get("sub"),
        "create_user",
        resource_type="user",
        resource_id=new_user["id"],
        details={"username": body.username, "role": body.role},
    )

    return new_user


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    body: UpdateUserRoleRequest,
    request: Request,
    user: Dict = Depends(require_permission("manage_users")),
):
    """Update a user's role (admin only)."""
    from services.admin_auth import update_user_role, log_audit

    pool = _get_db_pool(request)
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    updated = await update_user_role(pool, user_id, body.role)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    await log_audit(
        pool,
        user.get("sub"),
        "update_user",
        resource_type="user",
        resource_id=user_id,
        details={"new_role": body.role},
    )

    return updated


@router.delete("/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    request: Request,
    user: Dict = Depends(require_permission("manage_users")),
):
    """Delete a user (admin only)."""
    from services.admin_auth import delete_user, log_audit

    pool = _get_db_pool(request)
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    # Prevent self-deletion
    if user.get("sub") == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    deleted = await delete_user(pool, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    await log_audit(
        pool,
        user.get("sub"),
        "delete_user",
        resource_type="user",
        resource_id=user_id,
    )

    return {"status": "deleted", "user_id": user_id}


@router.get("/audit-log")
async def admin_get_audit_log(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict = Depends(require_permission("view_audit")),
):
    """Paginated audit log (admin only)."""
    from services.admin_auth import get_audit_log

    pool = _get_db_pool(request)
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    entries = await get_audit_log(pool, limit, offset)
    return {"entries": entries, "limit": limit, "offset": offset}


# ------------------------------------------------------------------
# Docling Serve Proxy endpoints
# ------------------------------------------------------------------

@router.post("/docling/convert")
async def admin_docling_convert(
    file: UploadFile = File(...),
    user: Dict = Depends(require_permission("upload")),
):
    """Proxy file conversion to Docling Serve."""
    saved_path = await _save_upload(file)
    try:
        from services.docling_client import DoclingClient
        client = DoclingClient()
        result = await client.convert_file(str(saved_path))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Docling conversion failed: {e}")


@router.get("/docling/status/{task_id}")
async def admin_docling_status(
    task_id: str,
    user: Dict = Depends(require_permission("view")),
):
    """Proxy to Docling Serve task status polling."""
    import httpx
    docling_url = os.getenv("DOCLING_SERVE_URL", "http://localhost:5001")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{docling_url}/v1/status/poll",
                params={"task_id": task_id},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Docling status check failed: {e}")


@router.get("/docling/health")
async def admin_docling_health(
    user: Dict = Depends(require_permission("view")),
):
    """Check Docling Serve health."""
    from services.docling_client import DoclingClient
    client = DoclingClient()
    return await client.health_check()


@router.get("/kb/images/{image_id}")
async def admin_get_image(
    image_id: str,
    user: Dict = Depends(require_permission("view")),
):
    """Serve an extracted document image."""
    filepath = _resolve_image_path(image_id)
    if not filepath:
        raise HTTPException(status_code=404, detail="Image not found")

    media_type = "image/jpeg" if filepath.suffix == ".jpg" else "application/octet-stream"
    return FileResponse(filepath, media_type=media_type)


@router.get("/kb/images/{collection}/{doc_id}/{image_id}")
async def admin_get_glm_image(
    collection: str,
    doc_id: str,
    image_id: str,
    user: Dict = Depends(require_permission("view")),
):
    """Serve GLM-OCR extracted PNG crops by collection/doc_id/image_id."""
    # Tight validation to prevent path traversal
    if not re.fullmatch(r"[A-Za-z0-9._\-]+", collection):
        raise HTTPException(status_code=400, detail="Invalid collection")
    if not re.fullmatch(r"[A-Za-z0-9._\-]+", doc_id):
        raise HTTPException(status_code=400, detail="Invalid doc_id")
    if not re.fullmatch(r"p\d+_img\d+", image_id):
        raise HTTPException(status_code=400, detail="Invalid image_id")

    filepath = IMAGE_DIR / collection / doc_id / f"{image_id}.png"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(filepath, media_type="image/png")


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _hierarchical_chunk(
    docling_result: Dict[str, Any],
    source_file: str,
    domain: str,
    uploaded_by: str,
    max_chunk_size: int = 1000,
    overlap: int = 200,
    images: Optional[List[Dict[str, str]]] = None,
    doc_id: Optional[str] = None,
    processing_method: str = "docling",
) -> List[Dict[str, Any]]:
    """
    Generic hierarchical chunking for non-Excel documents.
    Uses Docling's structured output to respect section boundaries.
    Links images to chunks based on <!-- image --> and <!-- image:ID --> placeholders.
    """
    doc = docling_result.get("document", docling_result)
    doc_id = doc_id or str(uuid.uuid4())

    # Try markdown first
    text = docling_result.get("md", "")
    if not text:
        parts = []
        for item in doc.get("content", []):
            t = item.get("text", "")
            if t:
                parts.append(t)
        text = "\n\n".join(parts)

    if not text:
        logger.warning(
            f"No text extracted from {source_file}. "
            f"docling_result keys: {list(docling_result.keys())}, "
            f"md field: {bool(docling_result.get('md'))}, "
            f"content items: {len(doc.get('content', []))}"
        )
        return []

    # 1) New placeholders: <!-- image:ID -->
    inline_image_positions: List[tuple[int, str]] = []
    for m in re.finditer(r"<!--\s*image:([^\s]+)\s*-->", text):
        inline_image_positions.append((m.start(), m.group(1)))

    # 2) Legacy placeholder: <!-- image --> mapped to extracted images list
    legacy_placeholder = "<!-- image -->"
    legacy_positions: List[int] = []
    search_start = 0
    while True:
        pos = text.find(legacy_placeholder, search_start)
        if pos == -1:
            break
        legacy_positions.append(pos)
        search_start = pos + len(legacy_placeholder)

    legacy_image_positions: List[tuple[int, Dict[str, str]]] = []
    if images and legacy_positions:
        if len(legacy_positions) == len(images):
            for pos, img in zip(legacy_positions, images):
                legacy_image_positions.append((pos, img))
        else:
            legacy_image_positions = [(0, img) for img in images]
    elif images and not legacy_positions:
        legacy_image_positions = [(0, img) for img in images]

    # Simple sliding-window chunking
    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            # Find images whose placeholder falls within [start, end)
            chunk_image_ids: List[str] = []
            # Inline IDs
            chunk_image_ids.extend([
                image_id for pos, image_id in inline_image_positions
                if start <= pos < end
            ])
            # Legacy mapped images
            chunk_image_ids.extend([
                img.get("image_id", "") for pos, img in legacy_image_positions
                if start <= pos < end
            ])
            chunk_image_ids = [i for i in chunk_image_ids if i]

            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "doc_id": doc_id,
                    "source_file": source_file,
                    "file_type": Path(source_file).suffix.lstrip("."),
                    "domain": domain,
                    "chunk_index": chunk_idx,
                    "uploaded_by": uploaded_by,
                    "upload_date": datetime.now(timezone.utc).isoformat(),
                    "processing_method": processing_method,
                    "has_images": len(chunk_image_ids) > 0,
                    "image_ids": list(dict.fromkeys(chunk_image_ids)),
                    "image_count": len(list(dict.fromkeys(chunk_image_ids))),
                },
            })
            chunk_idx += 1
        start = end - overlap if end < len(text) else end

    # Set total_chunks on all chunks
    for c in chunks:
        c["metadata"]["total_chunks"] = len(chunks)

    return chunks


# Image storage directory
IMAGE_DIR = UPLOAD_DIR / "images"


def _extract_and_save_images(
    docling_result: Dict[str, Any],
    doc_id: str,
    base_dir: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """
    Extract embedded images from Docling result, save as JPEG to disk.

    Returns list of dicts: {"image_id": ..., "path": ..., "page": ...}
    """
    pictures = docling_result.get("pictures", [])
    if not pictures:
        return []

    save_dir = (base_dir or IMAGE_DIR) / doc_id
    save_dir.mkdir(parents=True, exist_ok=True)

    images: List[Dict[str, str]] = []
    for idx, pic in enumerate(pictures):
        try:
            uri = pic.get("image", {}).get("uri", "")
            if not uri or "base64," not in uri:
                continue

            b64_data = uri.split("base64,", 1)[1]
            raw_bytes = base64.b64decode(b64_data)

            # Get page number from provenance
            prov = pic.get("prov", [{}])
            page_no = prov[0].get("page_no", 0) if prov else 0

            image_id = f"{doc_id}_page{page_no}_img{idx}"
            filename = f"page{page_no}_img{idx}.jpg"
            filepath = save_dir / filename

            # Convert to JPEG via Pillow
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(raw_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(filepath, "JPEG", quality=90)
            except Exception:
                # Fallback: save raw bytes
                filepath = save_dir / f"page{page_no}_img{idx}.bin"
                filepath.write_bytes(raw_bytes)

            images.append({
                "image_id": image_id,
                "path": str(filepath),
                "page": str(page_no),
            })

        except Exception as e:
            logger.warning(f"Skipping image {idx} in doc {doc_id}: {e}")
            continue

    return images


def _resolve_image_path(image_id: str) -> Optional[Path]:
    """Resolve an image_id like 'docid_page1_img0' to its file path."""
    page_match = re.search(r"^(.+)_(page\d+_img\d+)$", image_id)
    if not page_match:
        return None

    doc_id = page_match.group(1)
    filename = page_match.group(2) + ".jpg"

    filepath = IMAGE_DIR / doc_id / filename
    if filepath.exists():
        return filepath

    # Try .bin fallback
    bin_path = IMAGE_DIR / doc_id / (page_match.group(2) + ".bin")
    if bin_path.exists():
        return bin_path

    return None


async def _index_chunks(
    chunks: List[Dict[str, Any]], collection: str
) -> int:
    """Embed and index chunks into Qdrant. Returns count of indexed chunks."""
    import httpx
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance

    embeddings_url = os.getenv(
        "EMBEDDINGS_URL",
        os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
    )

    # Get embeddings for all chunks
    texts = [c["text"] for c in chunks]
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{embeddings_url}/embed",
                json={"inputs": texts},  # Fixed: API expects 'inputs' not 'texts'
            )
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return 0

    if len(embeddings) != len(chunks):
        logger.error(f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)}")
        return 0

    # Ensure collection exists
    qdrant = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )

    try:
        qdrant.get_collection(collection)
    except Exception:
        vector_size = len(embeddings[0]) if embeddings else 1024
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    # Upsert points
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point_id = str(uuid.uuid4())
        payload = {**chunk["metadata"], "text": chunk["text"]}
        points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

    qdrant.upsert(collection_name=collection, points=points)
    return len(points)


async def _index_chunks_with_enrichment(
    chunks: List[Dict[str, Any]],
    enrichment_results: Optional[List] = None,
    collection: str = "mold_reference_kb",
) -> int:
    """Embed and index chunks into Qdrant, optionally adding enriched points.

    When *enrichment_results* is provided (a list parallel to *chunks*), each
    non-None entry causes an additional "enriched" point to be created alongside
    the "original" point.  Enrichment metadata tags are applied to both points
    via ``qdrant.set_payload()``.

    When *enrichment_results* is ``None`` the function behaves identically to
    :func:`_index_chunks` (only original points are created).

    Returns the total number of points upserted.
    """
    import httpx
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance

    embeddings_url = os.getenv(
        "EMBEDDINGS_URL",
        os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
    )

    # ------------------------------------------------------------------
    # 1. Build parallel lists: texts to embed  +  point specs
    # ------------------------------------------------------------------
    texts: List[str] = []
    point_specs: List[Dict[str, Any]] = []  # chunk_index, chunk_type, text, metadata

    for i, chunk in enumerate(chunks):
        base_metadata = {**chunk["metadata"]}
        chunk_text = chunk["text"]

        # Original point
        texts.append(chunk_text)
        point_specs.append({
            "chunk_index": i,
            "chunk_type": "original",
            "text": chunk_text,
            "metadata": base_metadata,
        })

        # Enriched point (only when enrichment was performed and succeeded)
        if (
            enrichment_results is not None
            and i < len(enrichment_results)
            and enrichment_results[i] is not None
        ):
            enriched_text = enrichment_results[i].to_enriched_text()
            texts.append(enriched_text)
            point_specs.append({
                "chunk_index": i,
                "chunk_type": "enriched",
                "text": enriched_text,
                "metadata": {**base_metadata},
            })

    if not texts:
        return 0

    # ------------------------------------------------------------------
    # 2. Embed all texts in one batch call
    # ------------------------------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{embeddings_url}/embed",
                json={"inputs": texts},  # Fixed: API expects 'inputs' not 'texts'
            )
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return 0

    if len(embeddings) != len(texts):
        logger.error(
            f"Embedding count mismatch: {len(embeddings)} vs {len(texts)}"
        )
        return 0

    # ------------------------------------------------------------------
    # 3. Ensure Qdrant collection exists
    # ------------------------------------------------------------------
    qdrant = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )

    try:
        qdrant.get_collection(collection)
    except Exception:
        vector_size = len(embeddings[0]) if embeddings else 1024
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    # ------------------------------------------------------------------
    # 4. Build PointStruct list and upsert
    # ------------------------------------------------------------------
    points: List[PointStruct] = []
    point_ids_by_chunk: Dict[int, Dict[str, str]] = {}  # chunk_idx -> {type: point_id}

    for spec, embedding in zip(point_specs, embeddings):
        point_id = str(uuid.uuid4())
        payload = {
            **spec["metadata"],
            "text": spec["text"],
            "chunk_type": spec["chunk_type"],
        }
        points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        # Track point IDs by chunk index for later set_payload
        cidx = spec["chunk_index"]
        if cidx not in point_ids_by_chunk:
            point_ids_by_chunk[cidx] = {}
        point_ids_by_chunk[cidx][spec["chunk_type"]] = point_id

    qdrant.upsert(collection_name=collection, points=points)

    # ------------------------------------------------------------------
    # 5. Apply enrichment metadata tags to both original & enriched points
    # ------------------------------------------------------------------
    if enrichment_results is not None:
        for i, er in enumerate(enrichment_results):
            if er is None:
                continue
            enrichment_meta = er.to_metadata()
            if not enrichment_meta:
                continue

            ids_for_chunk = point_ids_by_chunk.get(i, {})
            for _ctype, pid in ids_for_chunk.items():
                try:
                    qdrant.set_payload(
                        collection_name=collection,
                        payload=enrichment_meta,
                        points=[pid],
                    )
                except Exception as e:
                    logger.warning(
                        f"set_payload failed for point {pid}: {e}"
                    )

    return len(points)


async def _delete_from_qdrant(doc_id: str, collection: str) -> int:
    """Delete all points matching a doc_id (or source filename) from Qdrant."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )

        # Try doc_id field first, fall back to source field
        for field in ("doc_id", "source"):
            points, _ = qdrant.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key=field, match=MatchValue(value=doc_id))]
                ),
                limit=1000,
                with_payload=False,
                with_vectors=False,
            )
            if points:
                qdrant.delete(
                    collection_name=collection,
                    points_selector=Filter(
                        must=[FieldCondition(key=field, match=MatchValue(value=doc_id))]
                    ),
                )
                return len(points)

        return 0
    except Exception as e:
        logger.error(f"Qdrant delete failed: {e}")
        return 0


async def _fallback_upload(
    saved_path: Path, filename: str, collection: str, domain: str
) -> Dict[str, Any]:
    """Fallback to legacy doc parsing service when Docling is unavailable."""
    from services.rag_pipeline.mold_document_ingester import MoldDocumentIngester
    from services.rag_pipeline.document_indexer import DocumentIndexer

    ingester = MoldDocumentIngester()
    result = await ingester.ingest_document(
        doc_path=saved_path, domain=domain, run_ocr=True
    )

    indexer = DocumentIndexer(
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
        embeddings_url=os.getenv(
            "EMBEDDINGS_URL",
            os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
        ),
        collection_name=collection,
    )
    await indexer.index_document(text=result["text"], metadata=result["metadata"])

    return {
        "status": "success",
        "filename": filename,
        "file_type": saved_path.suffix.lstrip("."),
        "chunks_extracted": 1,
        "chunks_indexed": 1,
        "collection": collection,
        "domain": domain,
        "processing_method": "legacy_ocr_fallback",
    }


async def _process_url_job(
    job_id: str,
    saved_path: Path,
    filename: str,
    body: UploadUrlRequest,
    user: Dict[str, Any],
    pool,
):
    """Background task: process a URL-downloaded file through the full pipeline.

    Stages: converting → chunking → enriching (optional) → indexing.
    Updates ``_batch_jobs[job_id]`` at each stage for polling.
    """
    from services.docling_client import DoclingClient
    from services.mold_case_extractor import MoldCaseExtractor

    job = _batch_jobs[job_id]

    try:
        # Stable doc_id for this URL document
        doc_id = str(uuid.uuid4())

        # ----- Stage 1: converting -----
        job["stage"] = "converting"
        ext = saved_path.suffix.lower()
        processing_method = "docling"

        if ext == ".pdf" and body.ocr_engine == "glm-ocr":
            docling_result, _, _ = await _process_with_glm_ocr(
                saved_path,
                body.domain,
                doc_id=doc_id,
                collection=body.collection,
            )
            processing_method = "glm-ocr"
        else:
            client = DoclingClient()
            options = client.options_for_format(ext)
            if body.ocr_engine != "easyocr":
                options["ocr_engine"] = body.ocr_engine

            docling_result = await client.convert_file(str(saved_path), options)

        # ----- Stage 2: chunking -----
        job["stage"] = "chunking"

        chunks: List[Dict[str, Any]] = []
        if body.domain == "mold" and ext in (".xlsx", ".xls"):
            extractor = MoldCaseExtractor()
            chunks = extractor.extract(
                docling_result,
                source_file=filename,
                uploaded_by=user.get("username", ""),
            )
        else:
            images = _extract_and_save_images(docling_result, doc_id=doc_id)
            chunks = _hierarchical_chunk(
                docling_result,
                source_file=filename,
                domain=body.domain,
                uploaded_by=user.get("username", ""),
                images=images,
                doc_id=doc_id,
                processing_method=processing_method,
            )

        # Inject source_url into all chunk metadata
        for chunk in chunks:
            chunk.setdefault("metadata", {})["source_url"] = body.url

        job["total_chunks"] = len(chunks)

        # ----- Stage 3: enriching (optional) -----
        enrichment_results = None
        if body.enrich and chunks:
            job["stage"] = "enriching"

            from services.llm_enrichment import enrich_document

            def _progress_callback(done: int, total: int):
                job["enriched_chunks"] = done
                job["enrichment_progress"] = f"{done}/{total}"

            enrichment_results = await enrich_document(
                chunks, body.domain, progress_callback=_progress_callback
            )

        # ----- Stage 4: indexing -----
        job["stage"] = "indexing"

        if chunks:
            if enrichment_results is not None:
                indexed = await _index_chunks_with_enrichment(
                    chunks, enrichment_results, body.collection
                )
            else:
                indexed = await _index_chunks_with_enrichment(
                    chunks, None, body.collection
                )
        else:
            indexed = 0

        job["completed"] = indexed
        job["status"] = "completed"

    except Exception as exc:
        logger.error(f"URL job {job_id} failed: {exc}", exc_info=True)
        job["status"] = "failed"
        job["error"] = str(exc)


# ------------------------------------------------------------------
# LLM Settings endpoints
# ------------------------------------------------------------------


def get_llm_config_service():
    from services.llm_config_service import LLMConfigService

    return LLMConfigService(encryption_key=os.getenv("ENCRYPTION_KEY"))


def _mask_api_key(key: str) -> str:
    if not key or len(key) < 12:
        return "***"
    return f"{key[:8]}...{key[-4:]}"


def _check_env_override(provider: str) -> bool:
    if provider == "nvidia":
        return bool(os.getenv("NVIDIA_API_KEY"))
    if provider == "openrouter":
        return bool(os.getenv("OPENROUTER_API_KEY"))
    if provider == "local_vllm":
        return bool(os.getenv("LLM_BASE_URL") or os.getenv("LLM_MODEL"))
    return False


@router.get("/settings/llm")
async def get_llm_config(user: Dict = Depends(require_permission("view"))):
    """Get active LLM configuration with masked API key."""
    try:
        service = get_llm_config_service()
        config = service.get_active_config()

        if config.get("api_key"):
            config["api_key_masked"] = _mask_api_key(config["api_key"])
            config.pop("api_key", None)

        config["env_override_active"] = _check_env_override(config.get("provider", ""))
        return config
    except Exception as exc:
        logger.error("Failed to get LLM config: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/settings/llm")
async def save_llm_config(
    request: LLMConfigRequest,
    user: Dict = Depends(require_permission("manage_settings")),
):
    """Save LLM configuration and invalidate manager cache for hot reload."""
    try:
        from services.llm_manager import LLMManager

        service = get_llm_config_service()
        config_id = service.save_config(
            provider=request.provider,
            model=request.model,
            api_key=request.api_key,
            base_url=request.base_url,
            parameters=request.parameters,
            user=user.get("username", "admin"),
        )

        LLMManager.get_instance().force_refresh()

        return {
            "success": True,
            "config_id": config_id,
            "message": "LLM configuration updated. New chat sessions will use this configuration.",
        }
    except Exception as exc:
        logger.error("Failed to save LLM config: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/settings/llm/models/{provider}")
async def get_provider_models(
    provider: str,
    user: Dict = Depends(require_permission("view")),
):
    """Get available model options for a provider."""
    try:
        service = get_llm_config_service()
        models = service.get_provider_models(provider)
        return {"models": models}
    except Exception as exc:
        logger.error("Failed to get provider models: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/settings/llm/test")
async def test_llm_connection(
    request: LLMConfigRequest,
    user: Dict = Depends(require_permission("view")),
):
    """Test provider connection before saving config."""
    # For NVIDIA API, use direct requests to match their API format exactly
    if "nvidia.com" in request.base_url:
        try:
            import httpx

            url = request.base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {request.api_key or 'test-key'}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": request.model,
                "messages": [{"role": "user", "content": "Say 'test' only"}],
                "max_tokens": 100,
                "temperature": 0.7,
                "top_p": 1.0,
                "stream": False,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "Connection successful",
                        "response": "NVIDIA API responded successfully",
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "message": "Invalid API key - Please set NVIDIA_API_KEY in .env or enter a valid key",
                    }
                elif response.status_code == 404:
                    return {
                        "success": False,
                        "message": f"Model '{request.model}' not found on NVIDIA API",
                    }
                else:
                    error_text = response.text[:200]
                    return {
                        "success": False,
                        "message": f"NVIDIA API error ({response.status_code}): {error_text}",
                    }
        except Exception as exc:
            return {"success": False, "message": f"Connection failed: {str(exc)}"}

    # For other providers (OpenRouter, local vLLM), use LangChain
    try:
        from langchain_openai import ChatOpenAI

        test_client = ChatOpenAI(
            base_url=request.base_url,
            api_key=request.api_key or "sk-no-key-required",
            model=request.model,
            timeout=10,
        )
        response = test_client.invoke("Say 'connection successful' and nothing else.")
        content = getattr(response, "content", str(response))

        return {
            "success": True,
            "message": "Connection successful",
            "response": str(content)[:100],
        }
    except Exception as exc:
        error_msg = str(exc)
        lowered = error_msg.lower()
        if "authentication" in lowered or "unauthorized" in lowered:
            return {"success": False, "message": "Invalid API key"}
        if "timeout" in lowered:
            return {
                "success": False,
                "message": "Connection timeout - check base URL and network",
            }
        return {"success": False, "message": f"Connection failed: {error_msg}"}


# ------------------------------------------------------------------
# Service Management endpoints
# ------------------------------------------------------------------


@router.get("/services")
async def admin_list_services(
    user: Dict = Depends(require_permission("view")),
):
    """List all services with their current status."""
    from services.service_manager import get_service_manager

    manager = get_service_manager()
    services = await manager.get_all_services()

    return {
        "services": [
            {
                "name": s.name,
                "display_name": s.display_name,
                "port": s.port,
                "status": s.status.value,
                "description": s.description,
                "pid": s.pid,
                "last_check": s.last_check.isoformat() if s.last_check else None,
                "health_details": s.health_details,
                "manageable": bool(s.process_pattern),
            }
            for s in services
        ]
    }


@router.get("/services/{service_name}")
async def admin_get_service(
    service_name: str,
    user: Dict = Depends(require_permission("view")),
):
    """Get detailed status of a specific service."""
    from services.service_manager import get_service_manager

    manager = get_service_manager()

    try:
        service = await manager.get_service_status(service_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

    return {
        "name": service.name,
        "display_name": service.display_name,
        "port": service.port,
        "status": service.status.value,
        "description": service.description,
        "start_script": service.start_script,
        "health_url": service.health_url,
        "pid": service.pid,
        "last_check": service.last_check.isoformat() if service.last_check else None,
        "health_details": service.health_details,
    }


@router.post("/services/{service_name}/start")
async def admin_start_service(
    service_name: str,
    user: Dict = Depends(require_permission("manage_services")),
):
    """Start a service."""
    from services.service_manager import get_service_manager
    from services.admin_auth import log_audit

    manager = get_service_manager()

    try:
        service = await manager.start_service(service_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start service: {e}")

    return {
        "name": service.name,
        "status": service.status.value,
        "port": service.port,
        "pid": service.pid,
        "message": f"Service '{service_name}' started successfully",
    }


@router.post("/services/{service_name}/stop")
async def admin_stop_service(
    service_name: str,
    user: Dict = Depends(require_permission("manage_services")),
):
    """Stop a service."""
    from services.service_manager import get_service_manager
    from services.admin_auth import log_audit

    manager = get_service_manager()

    try:
        service = await manager.stop_service(service_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stop service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {e}")

    return {
        "name": service.name,
        "status": service.status.value,
        "message": f"Service '{service_name}' stopped successfully",
    }


@router.post("/services/{service_name}/restart")
async def admin_restart_service(
    service_name: str,
    user: Dict = Depends(require_permission("manage_services")),
):
    """Restart a service."""
    from services.service_manager import get_service_manager
    from services.admin_auth import log_audit

    manager = get_service_manager()

    try:
        service = await manager.restart_service(service_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to restart service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart service: {e}")

    return {
        "name": service.name,
        "status": service.status.value,
        "port": service.port,
        "pid": service.pid,
        "message": f"Service '{service_name}' restarted successfully",
    }


async def _process_batch(
    job_id: str,
    files: List[Dict[str, Any]],
    collection: str,
    domain: str,
    user: Dict[str, Any],
    pool,
):
    """Background task: process each file in a batch upload job."""
    from services.docling_client import DoclingClient
    from services.mold_case_extractor import MoldCaseExtractor

    job = _batch_jobs[job_id]
    client = DoclingClient()

    for file_info in files:
        if file_info["status"] == "error":
            job["failed"] += 1
            continue

        try:
            path = Path(file_info["path"])
            ext = path.suffix.lower()
            options = client.options_for_format(ext)
            docling_result = await client.convert_file(str(path), options)

            if domain == "mold" and ext in (".xlsx", ".xls"):
                extractor = MoldCaseExtractor()
                chunks = extractor.extract(
                    docling_result,
                    source_file=file_info["filename"],
                    uploaded_by=user.get("username", ""),
                )
            else:
                chunks = _hierarchical_chunk(
                    docling_result,
                    source_file=file_info["filename"],
                    domain=domain,
                    uploaded_by=user.get("username", ""),
                )

            indexed = await _index_chunks(chunks, collection) if chunks else 0

            file_info["status"] = "completed"
            file_info["chunks"] = len(chunks)
            file_info["indexed"] = indexed
            job["completed"] += 1

        except Exception as e:
            logger.error(f"Batch file failed: {file_info['filename']}: {e}")
            file_info["status"] = "error"
            file_info["error"] = str(e)
            job["failed"] += 1

    job["status"] = "completed"
