import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# OpenTelemetry imports - MUST be before other imports for auto-instrumentation (when installed)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    OPENTELEMETRY_CORE_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_CORE_AVAILABLE = False

try:
    from openinference.instrumentation.langchain import LangChainInstrumentor
    OPENINFERENCE_AVAILABLE = True
except ImportError:
    OPENINFERENCE_AVAILABLE = False

OPENTELEMETRY_AVAILABLE = OPENTELEMETRY_CORE_AVAILABLE and OPENINFERENCE_AVAILABLE

if not OPENTELEMETRY_CORE_AVAILABLE:
    print("⚠️  OpenTelemetry core not available. Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp")
elif not OPENINFERENCE_AVAILABLE:
    print("⚠️  OpenTelemetry instrumentation not available. Install with: pip install openinference-instrumentation-langchain")

# Initialize OpenTelemetry if available
if OPENTELEMETRY_AVAILABLE:
    resource = Resource.create({
        "service.name": "bestbox-agent-api",
        "service.version": "1.0.0",
        "deployment.environment": "production"
    })

    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Export traces to OpenTelemetry Collector
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4317",  # OTel Collector gRPC endpoint
        insecure=True  # Use TLS in production
    )

    tracer_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )

    # Auto-instrument LangGraph
    LangChainInstrumentor().instrument()
    print("✅ OpenTelemetry instrumentation enabled")

# Initialize plugin system BEFORE importing graph
# This ensures plugins are loaded before graph is compiled
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from plugins import PluginRegistry, PluginLoader
    registry = PluginRegistry()
    loader = PluginLoader(registry, workspace_dir=os.getcwd())
    plugin_count = loader.load_all()
    logger.info(f"✅ Loaded {plugin_count} plugins before graph compilation")
except Exception as e:
    logger.error(f"⚠️  Plugin loading failed: {e}", exc_info=True)

from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union, cast
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agents.graph import app as agent_app, react_app
from agents.state import AgentState
from services.session_store import SessionStore
import uvicorn
import json
import time
import uuid
import asyncpg
import jwt
from datetime import datetime, timedelta

from pathlib import Path
import re

from services.tool_results_context import BESTBOX_TOOL_RESULTS_SESSION_ID

# Troubleshooting response validator - filters hallucinated case_ids
try:
    from services.troubleshooting.validator import validate_and_filter_results
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False
    logger.warning("Troubleshooting validator not available")

# Prometheus metrics
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from observability import (
        agent_requests,
        agent_latency,
        llm_tokens_generated,
        tool_execution_success,
        user_satisfaction,
        active_sessions,
        feedback_total,
        feedback_with_comment,
        http_errors_total,
        agent_response_seconds,
        tokens_total,
        tool_calls_total
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("⚠️  Prometheus metrics not available. Install with: pip install prometheus-client")

app = FastAPI(title="BestBox Agent API")

# Mount admin endpoints router (document management, KB, users, Docling proxy)
try:
    from services.admin_endpoints import router as admin_router
    app.include_router(admin_router)
    logger.info("✅ Admin endpoints router registered")
except Exception as e:
    logger.warning(f"⚠️  Admin endpoints router failed to load: {e}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# Database Connection Pool for Observability
# ==========================================================

db_pool: Optional[asyncpg.Pool] = None
session_store: Optional[SessionStore] = None

@app.on_event("startup")
async def startup():
    """Initialize database connection pool and register plugin HTTP routes on startup"""
    global db_pool, session_store

    # Register plugin HTTP routes (plugins already loaded at module level)
    try:
        from plugins import PluginRegistry
        registry = PluginRegistry()

        # Log loaded plugins
        plugins = registry.get_all_plugins()
        if plugins:
            logger.info(f"Active plugins: {', '.join([p.name for p in plugins])}")

        # Register plugin HTTP routes
        http_routes = registry.get_http_routes()
        for route_info in http_routes:
            plugin_name = route_info["plugin"]
            route = route_info["route"]
            handler = route_info["handler"]
            methods = route_info["methods"]

            # Register route dynamically
            for method in methods:
                if method == "GET":
                    app.get(route)(handler)
                elif method == "POST":
                    app.post(route)(handler)
                elif method == "PUT":
                    app.put(route)(handler)
                elif method == "DELETE":
                    app.delete(route)(handler)

            logger.info(f"Registered HTTP route: {route} from plugin {plugin_name}")

    except Exception as e:
        logger.error(f"⚠️  Plugin HTTP route registration failed: {e}", exc_info=True)

    try:
        db_pool = await asyncpg.create_pool(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            user=os.getenv('POSTGRES_USER', 'bestbox'),
            password=os.getenv('POSTGRES_PASSWORD', 'bestbox'),
            database=os.getenv('POSTGRES_DB', 'bestbox'),
            min_size=2,
            max_size=10
        )
        app.state.db_pool = db_pool
        logger.info("✅ Database connection pool initialized")

        try:
            from services.admin_auth import init_admin_tables
            await init_admin_tables(db_pool)
            logger.info("✅ Admin RBAC tables initialized")
        except Exception as e:
            logger.warning(f"⚠️  Admin RBAC init failed: {e}")

    except Exception as e:
        logger.warning(f"⚠️  Database connection failed: {e}. Observability logging will be disabled.")
        db_pool = None
        app.state.db_pool = None

    if os.getenv("SESSION_STORE_ENABLED", "true").lower() == "true":
        try:
            session_store = await SessionStore.create()
            logger.info("✅ Session store initialized")
        except Exception as e:
            logger.warning(f"⚠️  Session store init failed: {e}")
            session_store = None

@app.on_event("shutdown")
async def shutdown():
    """Close database connection pool on shutdown"""
    global db_pool, session_store
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")
    if session_store:
        await session_store.close()
        logger.info("Session store closed")

async def log_conversation(
    session_id: str,
    user_id: str,
    user_message: str,
    agent_response: str,
    agent_type: str,
    tool_calls: list,
    latency_ms: int,
    confidence: float,
    trace_id: str
):
    """
    Log conversation to PostgreSQL for audit trail.
    Runs asynchronously to not block API response.
    """
    if not db_pool:
        return  # Database not available

    try:
        async with db_pool.acquire() as conn:
            # Upsert session record
            await conn.execute("""
                INSERT INTO user_sessions (session_id, user_id, total_messages, last_active_at)
                VALUES ($1, $2, 1, NOW())
                ON CONFLICT (session_id) DO UPDATE
                SET total_messages = user_sessions.total_messages + 1,
                    last_active_at = NOW(),
                    agents_used = user_sessions.agents_used || jsonb_build_object($3,
                        COALESCE((user_sessions.agents_used->>$3)::int, 0) + 1
                    )
            """, session_id, user_id, agent_type)

            # Insert conversation record
            await conn.execute("""
                INSERT INTO conversation_log (
                    session_id, user_message, agent_response, agent_type,
                    tool_calls, latency_ms, confidence, trace_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                session_id,
                user_message,
                agent_response,
                agent_type,
                json.dumps(tool_calls),
                latency_ms,
                confidence,
                trace_id
            )
    except Exception as e:
        logger.error(f"Failed to log conversation: {e}")

class ChatMessage(BaseModel):
    role: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None  # Support both string and array format, optional
    tool_calls: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None

class ChatRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = None  # OpenAI format
    input: Optional[List[Dict[str, Any]]] = None  # CopilotKit format
    model: Optional[str] = None
    thread_id: Optional[str] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None  # For force_domain, query_type, etc.

class ChatResponse(BaseModel):
    response: str
    agent: str
    trace: List[Dict[str, Any]] = []

@app.get("/health")
async def health():
    return {"status": "ok", "service": "langgraph-agent"}


@app.get("/debug/env")
async def debug_env():
    """Temporary debug endpoint to check environment variables."""
    return {
        "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME"),
        "ADMIN_PASSWORD_SET": bool(os.getenv("ADMIN_PASSWORD")),
        "ADMIN_PASSWORD_LENGTH": len(os.getenv("ADMIN_PASSWORD", "")),
        "JWT_SECRET_SET": bool(os.getenv("JWT_SECRET_KEY")),
    }


@app.get("/v1/tool-results/latest")
async def get_latest_tool_results(
    session_id: Optional[str] = Query(default=None),
    after_ms: Optional[int] = Query(default=None),
    result_id: Optional[str] = Query(default=None),
):
    """Get the latest tool results for frontend rendering.
    Called by frontend after receiving a message to get full tool results."""
    try:
        from tools.troubleshooting_tools import get_latest_full_results
        results = get_latest_full_results(session_id=session_id, after_ms=after_ms, result_id=result_id)
        if results:
            return {"status": "ok", "data": results}
        return {"status": "ok", "data": None}
    except ImportError:
        return {"status": "error", "message": "Tool results not available"}


@app.delete("/v1/tool-results/clear")
async def clear_tool_results(session_id: Optional[str] = Query(default=None)):
    """Clear the tool results cache. Called on frontend session start."""
    try:
        from tools.troubleshooting_tools import clear_latest_results
        clear_latest_results(session_id=session_id)
        return {"status": "ok", "message": "Tool results cache cleared"}
    except ImportError:
        return {"status": "error", "message": "Tool results not available"}


def _safe_filename(original_name: str) -> str:
    """Normalize uploaded filenames to avoid path traversal and weird characters."""
    name = Path(original_name).name
    # Keep common characters only
    name = re.sub(r"[^A-Za-z0-9._()\-\u4e00-\u9fff]", "_", name)
    # Avoid empty or dotfiles
    if not name or name in {".", ".."}:
        name = f"upload_{uuid.uuid4().hex}.xlsx"
    return name


@app.post("/admin/troubleshooting/upload-xlsx")
async def admin_upload_troubleshooting_xlsx(
    file: UploadFile = File(...),
    index: bool = Query(True, description="If true, index extracted case into Qdrant"),
    output_dir: str = Query(
        "data/troubleshooting/processed",
        description="Where to write extracted JSON and images (relative to repo root)",
    ),
):
    """Admin endpoint to ingest a single troubleshooting XLSX into the KB pipeline."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    safe_name = _safe_filename(file.filename)
    if not safe_name.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    repo_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uploads_dir = repo_root / "data" / "troubleshooting" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    saved_path = uploads_dir / f"{int(time.time())}_{uuid.uuid4().hex}_{safe_name}"

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty upload")
        # Basic guardrail (~50MB)
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (max 50MB)")

        saved_path.write_bytes(content)

        from services.troubleshooting.excel_extractor import ExcelTroubleshootingExtractor
        from services.troubleshooting.indexer import TroubleshootingIndexer

        processed_output_dir = (repo_root / output_dir).resolve()
        extractor = ExcelTroubleshootingExtractor(output_dir=processed_output_dir)
        case_data = extractor.extract_case(saved_path)

        indexing_stats = None
        if index:
            indexer = TroubleshootingIndexer(
                qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
                qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
                embeddings_url=os.getenv(
                    "EMBEDDINGS_URL",
                    os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
                ),
            )
            indexing_stats = indexer.index_case(case_data)

        return {
            "status": "ok",
            "uploaded_filename": safe_name,
            "saved_path": str(saved_path),
            "case_id": case_data.get("case_id"),
            "total_issues": case_data.get("total_issues"),
            "source_file": case_data.get("source_file"),
            "indexed": bool(index),
            "indexing": indexing_stats,
            "output_dir": str(processed_output_dir),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin XLSX ingest failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


@app.post("/admin/troubleshooting/process-sample")
async def admin_process_sample_troubleshooting_xlsx(
    index: bool = Query(True, description="If true, index extracted case into Qdrant"),
):
    """Admin endpoint to process the built-in sample troubleshooting XLSX on the server."""

    repo_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sample_path = repo_root / "docs" / "1947688(ED736A0501)-case.xlsx"

    if not sample_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Sample file not found: {sample_path.name}"
        )

    try:
        from services.troubleshooting.excel_extractor import ExcelTroubleshootingExtractor
        from services.troubleshooting.indexer import TroubleshootingIndexer

        processed_output_dir = (repo_root / "data" / "troubleshooting" / "processed").resolve()
        extractor = ExcelTroubleshootingExtractor(output_dir=processed_output_dir)
        case_data = extractor.extract_case(sample_path)

        indexing_stats = None
        if index:
            indexer = TroubleshootingIndexer(
                qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
                qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
                embeddings_url=os.getenv(
                    "EMBEDDINGS_URL",
                    os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
                ),
            )
            indexing_stats = indexer.index_case(case_data)

        return {
            "status": "ok",
            "sample_filename": sample_path.name,
            "sample_path": str(sample_path),
            "case_id": case_data.get("case_id"),
            "total_issues": case_data.get("total_issues"),
            "source_file": case_data.get("source_file"),
            "indexed": bool(index),
            "indexing": indexing_stats,
            "output_dir": str(processed_output_dir),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin sample processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sample processing failed: {str(e)}")

# ==========================================================
# Direct Troubleshooting Query Endpoint (Performance Optimization)
# ==========================================================
# Bypasses agent entirely for structured queries, saving 1-3 seconds

class TroubleshootingQueryRequest(BaseModel):
    """Request model for direct troubleshooting queries."""
    query: str
    mode: Optional[str] = "AUTO"  # AUTO, STRUCTURED, SEMANTIC, HYBRID
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None
    return_sql: bool = False


class TroubleshootingQueryResponse(BaseModel):
    """Response model for direct troubleshooting queries."""
    query: str
    expanded_query: str
    mode: str
    total_found: int
    results: List[Dict[str, Any]]
    generated_sql: Optional[str] = None
    latency_ms: int


@app.post("/v1/troubleshooting/query", response_model=TroubleshootingQueryResponse)
async def direct_troubleshooting_query(request: TroubleshootingQueryRequest):
    """
    Direct troubleshooting query endpoint - bypasses agent for faster responses.

    Use this endpoint for structured queries (counts, filters) where full agent
    reasoning is not needed. Saves 1-3 seconds compared to /v1/chat/completions.

    Query types:
    - STRUCTURED: SQL queries (counts, filters, aggregations)
    - SEMANTIC: Vector search (similarity, concepts)
    - HYBRID: Both SQL + vector with result fusion
    - AUTO: Let system detect best approach

    Examples:
    - "有多少个披锋问题" → STRUCTURED (count query)
    - "披锋怎么解决" → SEMANTIC (how-to query)
    - "HIPS材料的披锋解决方案" → HYBRID (filtered semantic)
    """
    import time
    start_time = time.time()

    try:
        from services.troubleshooting.hybrid_searcher import HybridSearcher

        searcher = HybridSearcher(
            pg_host=os.getenv("POSTGRES_HOST", "localhost"),
            pg_port=int(os.getenv("POSTGRES_PORT", "5432")),
            pg_database=os.getenv("POSTGRES_DB", "bestbox"),
            pg_user=os.getenv("POSTGRES_USER", "bestbox"),
            pg_password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
            qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            llm_url=os.getenv("LLM_BASE_URL", "http://localhost:8001"),
            embeddings_url=os.getenv("EMBEDDINGS_URL", "http://localhost:8004"),
        )

        result = searcher.search(
            query=request.query,
            mode=request.mode,  # type: ignore
            top_k=request.top_k,
            filters=request.filters,
            return_sql=request.return_sql,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return TroubleshootingQueryResponse(
            query=result["query"],
            expanded_query=result["expanded_query"],
            mode=result["mode"],
            total_found=result["total_found"],
            results=result["results"],
            generated_sql=result.get("generated_sql"),
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Direct troubleshooting query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/troubleshooting/images/{image_id}")
async def get_troubleshooting_image(image_id: str):
    """
    Serve troubleshooting case images.
    Images are stored in data/troubleshooting/processed/images/

    Handles both prefixed (with timestamp) and non-prefixed image IDs.
    """
    import os
    from pathlib import Path
    from fastapi.responses import FileResponse

    # Sanitize image_id to prevent directory traversal
    if ".." in image_id or "/" in image_id or "\\" in image_id:
        raise HTTPException(status_code=400, detail="Invalid image ID")

    images_dir = Path(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "troubleshooting",
            "processed",
            "images",
        )
    )

    import re

    requested = Path(image_id).name
    requested_stem = requested
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if requested_stem.lower().endswith(ext):
            requested_stem = requested_stem[: -len(ext)]
            break

    # Try 1: Exact file match (including extension if provided)
    if "." in requested:
        exact_path = (images_dir / requested).resolve()
        if images_dir.resolve() in exact_path.parents or images_dir.resolve() == exact_path.parent:
            if exact_path.exists() and exact_path.is_file():
                suffix = exact_path.suffix.lower()
                media_type = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                }.get(suffix, "application/octet-stream")
                return FileResponse(str(exact_path), media_type=media_type)

    # Try 2: Glob search for prefixed/suffixed files
    # This handles old Qdrant index entries that point to non-prefixed filenames
    # when actual files have timestamp prefixes
    # E.g., index says "1947688(ED736A0501)-case_img023.jpg"
    #       but files are "*_1947688(ED736A0501)-case_img023.jpg"
    patterns: list[str] = [
        f"*{requested}",  # Match anything containing the requested name (with extension)
        f"*{requested_stem}*",  # Also try without extension
    ]

    # Try 3: If request includes an internal number that doesn't exist on disk,
    # fall back to ANY internal number for the same part/image index.
    # Example request: 1947688(ED736A0502)-case_img018
    # Existing files:   *_1947688(ED736A0501)-case_img018.jpg
    m = re.search(r"(?P<part>\d+)\([^)]*\)-case_img(?P<imgnum>\d{3})$", requested_stem)
    if m:
        part = m.group("part")
        imgnum = m.group("imgnum")
        # The '(' is literal in filenames; use '*' to match any internal number inside parentheses.
        patterns.extend(
            [
                f"*{part}(*-case_img{imgnum}.jpg",
                f"*{part}(*-case_img{imgnum}.jpeg",
                f"*{part}(*-case_img{imgnum}.png",
                f"*{part}(*-case_img{imgnum}.webp",
            ]
        )
    
    for pattern in patterns:
        matching_files = [p for p in images_dir.glob(pattern) if p.is_file()]

        # Prefer newest file (multiple uploads can produce duplicates)
        matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for img_file in matching_files:
            if not img_file.is_file():
                continue
            
            # Verify it doesn't traverse outside images_dir
            if images_dir.resolve() not in img_file.resolve().parents and images_dir.resolve() != img_file.resolve().parent:
                continue
            
            suffix = img_file.suffix.lower()
            media_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }.get(suffix, "application/octet-stream")
            return FileResponse(str(img_file), media_type=media_type)

    raise HTTPException(status_code=404, detail="Image not found")


# ==========================================================
# VLM Service Integration
# ==========================================================

# Import VLM components
try:
    from services.vlm import VLMJobStore, VLMResult
    from services.vlm.models import VLMWebhookPayload, JobStatus
    import hmac
    import hashlib
    VLM_AVAILABLE = True
except ImportError:
    VLM_AVAILABLE = False
    logger.warning("⚠️  VLM service components not available")

# VLM job store instance
_vlm_job_store: Optional["VLMJobStore"] = None


def get_vlm_job_store() -> "VLMJobStore":
    """Get or create VLM job store instance"""
    global _vlm_job_store
    if _vlm_job_store is None and VLM_AVAILABLE:
        _vlm_job_store = VLMJobStore()
    return _vlm_job_store


def verify_vlm_signature(body: bytes, signature: str) -> bool:
    """
    Verify VLM webhook signature using HMAC-SHA256.

    Args:
        body: Request body bytes
        signature: X-VLM-Signature header value (format: sha256=<hex>)

    Returns:
        True if signature is valid
    """
    secret = os.getenv("VLM_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("VLM_WEBHOOK_SECRET not configured, skipping signature verification")
        return True

    if not signature.startswith("sha256="):
        return False

    expected_sig = signature[7:]  # Remove "sha256=" prefix
    computed_sig = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


class VLMWebhookRequest(BaseModel):
    """VLM webhook callback payload"""
    event: str
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    completed_at: Optional[str] = None


@app.post("/api/v1/webhooks/vlm-results")
async def vlm_webhook_receiver(
    request: Request,
    x_vlm_signature: Optional[str] = Header(None, alias="X-VLM-Signature"),
    x_vlm_job_id: Optional[str] = Header(None, alias="X-VLM-Job-ID")
):
    """
    Receive VLM job completion callbacks.

    The VLM service calls this endpoint when a job completes.
    Results are stored in Redis for retrieval by the VLM client.
    """
    if not VLM_AVAILABLE:
        raise HTTPException(status_code=503, detail="VLM service not available")

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature if configured
    if x_vlm_signature and not verify_vlm_signature(body, x_vlm_signature):
        logger.warning(f"Invalid VLM webhook signature for job {x_vlm_job_id}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
        webhook_data = VLMWebhookRequest(**payload)
    except Exception as e:
        logger.error(f"Failed to parse VLM webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    job_store = get_vlm_job_store()
    job_id = webhook_data.job_id

    logger.info(f"Received VLM webhook for job {job_id}: {webhook_data.event}")

    if webhook_data.status == "completed" and webhook_data.result:
        # Store successful result
        try:
            result = VLMResult(**webhook_data.result)
            await job_store.store_result(job_id, result)
            logger.info(f"Stored VLM result for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to store VLM result for {job_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to store result: {e}")

    elif webhook_data.status == "failed":
        # Store error
        error_msg = webhook_data.error or "Unknown error"
        await job_store.store_error(job_id, error_msg)
        logger.warning(f"VLM job {job_id} failed: {error_msg}")

    return {"status": "ok", "job_id": job_id}


@app.post("/api/v1/upload")
async def upload_file_for_analysis(
    file: UploadFile = File(...),
    analysis_type: str = Query("vlm", description="Type of analysis: 'vlm' for VLM processing")
):
    """
    Upload a file for VLM analysis.

    This endpoint saves uploaded files temporarily for processing by the VLM service.
    Returns the file path that can be used with analysis tools.

    Supported file types: jpg, jpeg, png, webp, pdf, xlsx
    Max file size: 50MB
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Validate file type
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".xlsx"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}"
        )

    # Read and validate size
    content = await file.read()
    max_size = 50 * 1024 * 1024  # 50MB
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File too large. Max size: {max_size // (1024*1024)}MB")

    # Create upload directory
    repo_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uploads_dir = repo_root / "data" / "vlm_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    safe_name = re.sub(r"[^A-Za-z0-9._()\-\u4e00-\u9fff]", "_", Path(file.filename).name)
    unique_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_name}"
    file_path = uploads_dir / unique_name

    # Save file
    file_path.write_bytes(content)

    logger.info(f"Uploaded file for VLM analysis: {file_path}")

    return {
        "status": "ok",
        "filename": safe_name,
        "file_path": str(file_path),
        "size_bytes": len(content),
        "analysis_type": analysis_type
    }


@app.get("/api/v1/vlm/jobs/{job_id}")
async def get_vlm_job_status(job_id: str):
    """
    Get status of a VLM analysis job.

    Returns the job status and result if completed.
    """
    if not VLM_AVAILABLE:
        raise HTTPException(status_code=503, detail="VLM service not available")

    job_store = get_vlm_job_store()

    # Check status
    status = await job_store.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    response = {
        "job_id": job_id,
        "status": status.value
    }

    if status == JobStatus.COMPLETED:
        result = await job_store.get_result(job_id)
        if result:
            response["result"] = result.model_dump()

    elif status == JobStatus.FAILED:
        error = await job_store.get_error(job_id)
        if error:
            response["error"] = error

    return response


@app.get("/health/vlm")
async def health_check_vlm():
    """
    VLM service connectivity health check.
    """
    if not VLM_AVAILABLE:
        return {"status": "unavailable", "error": "VLM components not installed"}

    vlm_enabled = os.getenv("VLM_ENABLED", "false").lower() == "true"
    if not vlm_enabled:
        return {"status": "disabled", "message": "VLM_ENABLED=false"}

    try:
        from services.vlm import VLMServiceClient
        client = VLMServiceClient()
        health = await client.check_health()
        await client.close()
        return {
            "status": "healthy",
            "vlm_status": health.status,
            "model": health.model,
            "queue_depth": health.queue_depth
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/health/db")
async def health_check_database():
    """
    Database connectivity health check.
    Used by SystemStatus component in admin UI.
    """
    if not db_pool:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "error": "Database pool not initialized"}
        )

    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "error": str(e)}
        )

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Scraped by Prometheus every 15 seconds.
    """
    if not PROMETHEUS_AVAILABLE:
        return Response(content="Prometheus metrics not available", status_code=503)

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

class FeedbackRequest(BaseModel):
    message_id: str  # Currently unused (could link to specific message ID in future)
    session_id: str
    rating: str  # 'positive' or 'negative'

@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Record user feedback for the most recent message in a session.
    """
    # Validate rating
    if request.rating not in ['positive', 'negative']:
        raise HTTPException(status_code=400, detail="Rating must be 'positive' or 'negative'")

    # Update Prometheus counter (real-time metrics)
    if PROMETHEUS_AVAILABLE:
        user_satisfaction.labels(rating=request.rating).inc()

    # Update PostgreSQL (audit trail)
    if not db_pool:
        return {"status": "success", "message": "Feedback recorded (metrics only)"}

    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                UPDATE conversation_log
                SET user_feedback = $1
                WHERE session_id = $2
                  AND id = (
                      SELECT id
                      FROM conversation_log
                      WHERE session_id = $2
                      ORDER BY timestamp DESC
                      LIMIT 1
                  )
                RETURNING id, agent_type, latency_ms
            """, request.rating, request.session_id)

            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="No conversation found for this session"
                )

        return {
            "status": "success",
            "message": "Feedback recorded",
            "conversation_id": result['id']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        return {"status": "success", "message": "Feedback recorded (metrics only)"}


# ==========================================================
# Enhanced Feedback API (Phase 3)
# ==========================================================

class DetailedFeedbackRequest(BaseModel):
    session_id: str
    message_id: Optional[str] = None
    feedback_type: str  # 'positive' or 'negative'
    comment: Optional[str] = None
    agent_type: Optional[str] = None

@app.post("/api/feedback")
async def submit_detailed_feedback(request: DetailedFeedbackRequest):
    """
    Submit detailed feedback with optional comment.
    Stores in PostgreSQL feedback table and updates Prometheus metrics.
    """
    if request.feedback_type not in ['positive', 'negative']:
        raise HTTPException(status_code=400, detail="feedback_type must be 'positive' or 'negative'")

    agent = request.agent_type or "unknown"

    # Update Prometheus metrics
    if PROMETHEUS_AVAILABLE:
        feedback_total.labels(feedback_type=request.feedback_type, agent_type=agent).inc()
        user_satisfaction.labels(rating=request.feedback_type).inc()
        if request.comment:
            feedback_with_comment.labels(feedback_type=request.feedback_type).inc()

    if not db_pool:
        return {"status": "success", "id": None, "message": "Feedback recorded (metrics only)"}

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO feedback (session_id, message_id, feedback_type, comment, agent_type)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, request.session_id, request.message_id, request.feedback_type,
                request.comment, agent)
            return {
                "status": "success",
                "id": row['id'],
                "message": "Feedback recorded"
            }
    except Exception as e:
        logger.error(f"Failed to store detailed feedback: {e}")
        return {"status": "success", "id": None, "message": "Feedback recorded (metrics only)"}

@app.get("/api/feedback/{session_id}")
async def get_session_feedback(session_id: str):
    """
    Retrieve all feedback entries for a session.
    """
    if not db_pool:
        return {"entries": [], "total": 0}

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, session_id, message_id, feedback_type, comment, agent_type, created_at
                FROM feedback
                WHERE session_id = $1
                ORDER BY created_at DESC
            """, session_id)
            entries = [dict(r) for r in rows]
            # Convert datetime objects to ISO strings
            for entry in entries:
                if entry.get('created_at'):
                    entry['created_at'] = entry['created_at'].isoformat()
            return {"entries": entries, "total": len(entries)}
    except Exception as e:
        logger.error(f"Failed to fetch feedback: {e}")
        return {"entries": [], "total": 0}

@app.get("/api/feedback")
async def get_all_feedback(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    feedback_type: Optional[str] = Query(default=None),
):
    """
    List all feedback entries with optional filtering.
    Used by the admin dashboard feedback panel.
    """
    if not db_pool:
        return {"entries": [], "total": 0}

    try:
        async with db_pool.acquire() as conn:
            conditions = []
            params: list = []
            idx = 1

            if feedback_type:
                conditions.append(f"feedback_type = ${idx}")
                params.append(feedback_type)
                idx += 1

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            count_row = await conn.fetchrow(f"SELECT COUNT(*) FROM feedback {where}", *params)
            total = count_row['count']

            params.extend([limit, offset])
            rows = await conn.fetch(f"""
                SELECT id, session_id, message_id, feedback_type, comment, agent_type, created_at
                FROM feedback
                {where}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}
            """, *params)

            entries = [dict(r) for r in rows]
            for entry in entries:
                if entry.get('created_at'):
                    entry['created_at'] = entry['created_at'].isoformat()

            return {"entries": entries, "total": total}
    except Exception as e:
        logger.error(f"Failed to fetch feedback list: {e}")
        return {"entries": [], "total": 0}


@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    return {
        "object": "list",
        "data": [
            {
                "id": "bestbox-agent",
                "object": "model",
                "created": 1234567890,
                "owned_by": "bestbox"
            }
        ]
    }

@app.post("/v1/responses")
async def create_response(
    request: ChatRequest,
    bbx_session: Optional[str] = Header(None, alias="X-BBX-Session"),
):
    """
    OpenAI Responses API endpoint for CopilotKit v1.50+.
    Uses the new event-based streaming format.
    """
    session_id_override: Optional[str] = None
    if bbx_session:
        session_id_override = f"ui-{bbx_session}"
    elif request.thread_id:
        session_id_override = request.thread_id
    if request.stream:
        return await responses_api_stream(request, session_id_override=session_id_override)
    else:
        return await chat_completion(request)

async def responses_api_stream(request: ChatRequest, session_id_override: Optional[str] = None):
    """Stream the response using OpenAI Responses API format for CopilotKit"""
    async def generate():
        response_id = f"resp_{uuid.uuid4().hex[:24]}"
        item_id = f"msg_{uuid.uuid4().hex[:24]}"
        
        try:
            request_start_ms = int(time.time() * 1000)
            # Process the request
            messages_to_process = []
            
            if request.messages:
                messages_to_process = request.messages
            elif request.input:
                for item in request.input:
                    if isinstance(item, dict) and "role" in item:
                        content = item.get("content", "")
                        msg = ChatMessage(role=item["role"], content=content)
                        if "tool_calls" in item:
                            msg.tool_calls = item["tool_calls"]
                        messages_to_process.append(msg)
            
            if not messages_to_process:
                yield f"data: {json.dumps({'type': 'error', 'error': {'message': 'No messages provided'}})}\n\n"
                return
            
            # Convert to LangChain messages
            lc_messages = []
            for msg in messages_to_process:
                content_text = parse_message_content(msg.content) if msg.content is not None else ""
                
                if msg.role == "user":
                    lc_messages.append(HumanMessage(content=content_text))
                elif msg.role == "assistant":
                    tool_calls = msg.tool_calls or []
                    lc_messages.append(AIMessage(content=content_text, tool_calls=tool_calls))
                elif msg.role == "system":
                    lc_messages.append(SystemMessage(content=content_text))
            
            # Extract optimization metadata
            force_domain = None
            query_type = None
            if request.metadata:
                force_domain = request.metadata.get("force_domain")
                query_type = request.metadata.get("query_type")

            inputs: AgentState = {
                "messages": lc_messages,
                "current_agent": "router",
                "tool_calls": 0,
                "confidence": 1.0,
                "context": {
                    "force_domain": force_domain,
                    "query_type": query_type,
                },
                "plan": [],
                "step": 0
            }

            # 1. Send response.created event
            created_event = {
                "type": "response.created",
                "response": {
                    "id": response_id,
                    "object": "response",
                    "created_at": int(time.time()),
                    "status": "in_progress",
                    "output": [],
                    "model": request.model or "bestbox-agent"
                }
            }
            yield f"data: {json.dumps(created_event)}\n\n"
            
            # 2. Send response.output_item.added event
            output_item_added = {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "id": item_id,
                    "type": "message",
                    "role": "assistant",
                    "content": []
                }
            }
            yield f"data: {json.dumps(output_item_added)}\n\n"
            
            # Scope tool-results storage to this request/session.
            session_id = session_id_override or request.thread_id or str(uuid.uuid4())
            token = BESTBOX_TOOL_RESULTS_SESSION_ID.set(session_id)
            try:
                result = await agent_app.ainvoke(cast(AgentState, inputs))
            finally:
                BESTBOX_TOOL_RESULTS_SESSION_ID.reset(token)
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            current_agent = result.get("current_agent", "unknown")

            # Ensure content is never undefined - always a string
            if content is None:
                content = ""

            # Embed full tool results for the UI (frontend extracts and renders).
            try:
                from tools.troubleshooting_tools import get_latest_full_results
                full_tool_results = get_latest_full_results(session_id=session_id, after_ms=request_start_ms - 1)
            except ImportError:
                full_tool_results = None
            if full_tool_results:
                tool_results_json = json.dumps([full_tool_results], ensure_ascii=False)
                content = f"[TOOL_RESULTS]{tool_results_json}[/TOOL_RESULTS]\n\n{content}"
            content = f"{content}\n\n[BBX_SESSION]{session_id}[/BBX_SESSION]"

            # Validate response - filter hallucinated case_ids
            if VALIDATOR_AVAILABLE and content and current_agent == "mold_agent":
                try:
                    content = validate_and_filter_results(content)
                except Exception as e:
                    logger.warning(f"Response validation failed in stream: {e}")

            # 3. Stream the content using response.output_text.delta events
            # Split content into chunks for a more natural streaming effect
            chunk_size = 20  # characters per chunk
            for i in range(0, len(content), chunk_size):
                chunk_text = content[i:i+chunk_size]
                delta_event = {
                    "type": "response.output_text.delta",
                    "item_id": item_id,
                    "output_index": 0,
                    "content_index": 0,
                    "delta": chunk_text
                }
                yield f"data: {json.dumps(delta_event)}\n\n"
            
            # 4. Send response.output_item.done event
            output_item_done = {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": item_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": content}]
                }
            }
            yield f"data: {json.dumps(output_item_done)}\n\n"
            
            # 5. Send response.completed event
            completed_event = {
                "type": "response.completed",
                "response": {
                    "id": response_id,
                    "object": "response",
                    "created_at": int(time.time()),
                    "status": "completed",
                    "output": [{
                        "id": item_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": content}]
                    }],
                    "model": request.model or "bestbox-agent",
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": len(content.split())
                    }
                }
            }
            yield f"data: {json.dumps(completed_event)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Responses API streaming error: {e}")
            error_event = {
                "type": "error",
                "sequence_number": 0,
                "error": {
                    "type": "server_error",
                    "message": str(e)
                }
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

async def chat_completion_stream(request: ChatRequest, session_id_override: Optional[str] = None):
    """Stream the response using SSE format"""
    async def generate():
        try:
            request_start_ms = int(time.time() * 1000)
            # Process the request
            messages_to_process = []

            if request.messages:
                messages_to_process = request.messages
            elif request.input:
                for item in request.input:
                    if isinstance(item, dict) and "role" in item:
                        content = item.get("content", "")
                        msg = ChatMessage(role=item["role"], content=content)
                        if "tool_calls" in item:
                            msg.tool_calls = item["tool_calls"]
                        messages_to_process.append(msg)

            if not messages_to_process:
                yield f"data: {json.dumps({'error': 'No messages provided'})}\n\n"
                return

            # Convert to LangChain messages
            lc_messages = []
            for msg in messages_to_process:
                content_text = parse_message_content(msg.content) if msg.content is not None else ""

                if msg.role == "user":
                    lc_messages.append(HumanMessage(content=content_text))
                elif msg.role == "assistant":
                    tool_calls = msg.tool_calls or []
                    lc_messages.append(AIMessage(content=content_text, tool_calls=tool_calls))
                elif msg.role == "system":
                    lc_messages.append(SystemMessage(content=content_text))

            # Extract optimization metadata
            force_domain = None
            query_type = None
            if request.metadata:
                force_domain = request.metadata.get("force_domain")
                query_type = request.metadata.get("query_type")

            inputs: AgentState = {
                "messages": lc_messages,
                "current_agent": "router",
                "tool_calls": 0,
                "confidence": 1.0,
                "context": {
                    "force_domain": force_domain,
                    "query_type": query_type,
                },
                "plan": [],
                "step": 0
            }

            # Scope tool-results storage to this request/session.
            session_id = session_id_override or request.thread_id or str(uuid.uuid4())
            token = BESTBOX_TOOL_RESULTS_SESSION_ID.set(session_id)
            try:
                result = await agent_app.ainvoke(cast(AgentState, inputs))
            finally:
                BESTBOX_TOOL_RESULTS_SESSION_ID.reset(token)
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            current_agent = result.get("current_agent", "unknown")

            # ==========================================================
            # OPTION A: Get full tool results from global cache
            # The tool stores condensed results in the message (for LLM context)
            # but keeps full results in a global cache (for frontend rendering)
            # ==========================================================
            try:
                from tools.troubleshooting_tools import get_latest_full_results
                full_tool_results = get_latest_full_results(session_id=session_id, after_ms=request_start_ms - 1)
                # Don't clear - frontend will fetch via /v1/tool-results/latest
            except ImportError:
                full_tool_results = None

            # Ensure content is never undefined - always a string
            if content is None:
                content = ""

            # Prepend full tool results as hidden data tag (frontend extracts and renders)
            if full_tool_results:
                tool_results_json = json.dumps([full_tool_results], ensure_ascii=False)
                content = f"[TOOL_RESULTS]{tool_results_json}[/TOOL_RESULTS]\n\n{content}"

            # Include session id for deterministic frontend fetch fallback.
            content = f"{content}\n\n[BBX_SESSION]{session_id}[/BBX_SESSION]"

            # Validate response - filter hallucinated case_ids
            if VALIDATOR_AVAILABLE and content and current_agent == "mold_agent":
                try:
                    content = validate_and_filter_results(content)
                except Exception as e:
                    logger.warning(f"Response validation failed in SSE stream: {e}")

            # Stream the content in small chunks to avoid SSE line-size
            # truncation in CopilotKit / OpenAI SDK pipelines.
            chunk_id = f"chatcmpl-{int(time.time())}"
            model_name = request.model or "bestbox-agent"
            chunk_size = 200  # characters per delta
            for i in range(0, len(content), chunk_size):
                chunk_text = content[i:i+chunk_size]
                delta: dict = {"content": chunk_text}
                if i == 0:
                    delta["role"] = "assistant"
                chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": delta,
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # Send finish chunk
            finish_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model or "bestbox-agent",
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(finish_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            # Return an error message as content so frontend doesn't crash
            error_chunk = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model or "bestbox-agent",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"Error: {str(e)}"
                    },
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


def parse_message_content(content: Union[str, List[Dict[str, Any]]]) -> str:
    """Parse message content from either string or array format"""
    if isinstance(content, str):
        text = content
        text = re.sub(r"\[TOOL_RESULTS\][\s\S]*?\[\/TOOL_RESULTS\]", "", text)
        text = re.sub(r"\[SPEECH\][\s\S]*?\[\/SPEECH\]", "", text)
        text = re.sub(r"\[BBX_SESSION\][\s\S]*?\[\/BBX_SESSION\]", "", text)
        return text.strip()
    elif isinstance(content, list):
        # Extract text from array format like [{"type": "input_text", "text": "hello"}]
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "input_text" and "text" in item:
                    text_parts.append(item["text"])
                elif "text" in item:
                    text_parts.append(item["text"])
        return " ".join(text_parts) if text_parts else str(content)
    else:
        return str(content)


def generate_admin_jwt(username: str, role: str = "admin") -> str:
    """Generate a JWT token for admin authentication."""
    secret = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token."""
    secret = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def verify_admin_token(token: str) -> None:
    """Verify admin token from request headers.

    Accepts both:
    - Static admin token from ADMIN_TOKEN env var
    - JWT tokens generated by /admin/auth/login
    """
    # Try static token first
    static_token = os.getenv("ADMIN_TOKEN")
    if static_token and token == static_token:
        return

    # Try JWT token
    try:
        payload = verify_jwt_token(token)
        # Verify it's an admin role
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def build_tool_calls_from_trace(reasoning_trace: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract tool calls from a reasoning trace."""
    tool_calls = []
    for step in reasoning_trace:
        if step.get("type") == "act":
            tool_calls.append(
                {
                    "tool": step.get("tool_name"),
                    "args": step.get("tool_args"),
                }
            )
    return tool_calls


@app.post("/chat")
async def chat_legacy_endpoint(
    request: ChatRequest,
    user_id: str = Header(default="anonymous", alias="x-user-id"),
    openclaw_session: Optional[str] = Header(None, alias="X-OpenClaw-Session"),
    openclaw_channel: Optional[str] = Header(None, alias="X-OpenClaw-Channel"),
    bbx_session: Optional[str] = Header(None, alias="X-BBX-Session"),
):
    """Legacy compatibility endpoint.

    Some clients post to `/chat`; route them to the OpenAI-compatible handler.
    FastAPI will extract these headers from the HTTP request, then we forward to the main handler.
    """
    return await chat_completion_endpoint(
        request=request,
        user_id=user_id,
        openclaw_session=openclaw_session,
        openclaw_channel=openclaw_channel,
        bbx_session=bbx_session,
    )


@app.post("/chat/react")
async def chat_react_endpoint(
    request: ChatRequest,
    user_id: str = Header(default="anonymous", alias="x-user-id"),
):
    """ReAct endpoint with visible reasoning trace."""
    if request.stream:
        return await chat_react_stream(request, user_id)

    start_time = time.time()
    
    if request.thread_id:
        session_id = request.thread_id
        if session_store:
            await session_store.ensure_session(session_id, user_id, "api")
    else:
        session_id = await session_store.create_session(user_id, "api") if session_store else str(uuid.uuid4())

    messages_to_process = []
    if request.messages:
        messages_to_process = request.messages
    elif request.input:
        for item in request.input:
            if isinstance(item, dict) and "role" in item:
                content = item.get("content", "")
                msg = ChatMessage(role=item["role"], content=content)
                if "tool_calls" in item:
                    msg.tool_calls = item["tool_calls"]
                messages_to_process.append(msg)
    else:
        raise HTTPException(status_code=422, detail="Either 'messages' or 'input' field is required")

    lc_messages = []
    user_message = ""
    for msg in messages_to_process:
        content_text = parse_message_content(msg.content) if msg.content is not None else ""
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=content_text))
            user_message = content_text
        elif msg.role == "assistant":
            tool_calls = msg.tool_calls or []
            lc_messages.append(AIMessage(content=content_text, tool_calls=tool_calls))
        elif msg.role == "system":
            lc_messages.append(SystemMessage(content=content_text))

    if not lc_messages:
        raise HTTPException(status_code=422, detail="No valid messages to process")

    inputs: AgentState = {
        "messages": lc_messages,
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {},
        "plan": [],
        "step": 0,
        "reasoning_trace": [],
        "session_id": session_id,
    }

    result = await react_app.ainvoke(cast(AgentState, inputs))
    last_msg = result["messages"][-1]
    content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    reasoning_trace = result.get("reasoning_trace", [])

    latency_ms = int((time.time() - start_time) * 1000)
    if session_store:
        await session_store.add_message(
            session_id=session_id,
            role="user",
            content=user_message,
        )
        await session_store.add_message(
            session_id=session_id,
            role="assistant",
            content=content or "",
            reasoning_trace=reasoning_trace,
            tool_calls=build_tool_calls_from_trace(reasoning_trace),
            metrics={"latency_ms": latency_ms},
        )

    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model or "bestbox-react",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content or "",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "session_id": session_id,
        "reasoning_trace": reasoning_trace,
    }


async def chat_react_stream(request: ChatRequest, user_id: str):
    """Stream ReAct response with reasoning steps."""
    async def generate():
        try:
            request_copy = request.model_copy(update={"stream": False})
            response = await chat_react_endpoint(request_copy, user_id)
            reasoning_trace = response.get("reasoning_trace", [])
            for step in reasoning_trace:
                yield f"data: {json.dumps({'type': 'reasoning_step', 'step': step})}\n\n"

            content = response["choices"][0]["message"]["content"]
            yield f"data: {json.dumps({'type': 'message', 'content': content})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"ReAct streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# Admin authentication models
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    user: Dict[str, str]


class SessionRatingRequest(BaseModel):
    rating: str
    note: Optional[str] = None


@app.post("/admin/auth/login")
async def admin_login(request: AdminLoginRequest):
    """Admin login endpoint.

    Validates credentials against environment variables and returns a JWT token.

    Environment variables:
    - ADMIN_USERNAME: Admin username (default: admin)
    - ADMIN_PASSWORD: Admin password (required in production)
    - JWT_SECRET_KEY: Secret key for signing JWTs (required in production)
    """
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD")

    if not expected_password:
        raise HTTPException(
            status_code=500,
            detail="Admin authentication not configured (missing ADMIN_PASSWORD)",
        )

    # Validate credentials
    if request.username != expected_username or request.password != expected_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate JWT token
    token = generate_admin_jwt(request.username, role="admin")

    return AdminLoginResponse(
        token=token,
        user={"username": request.username, "role": "admin"},
    )


@app.get("/admin/sessions")
async def admin_list_sessions(
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    admin_token: str = Header(..., alias="admin-token"),
):
    """List sessions for admin review."""
    verify_admin_token(admin_token)
    if not session_store:
        raise HTTPException(status_code=503, detail="Session store unavailable")
    return await session_store.list_sessions(limit, offset, user_id, status)


@app.get("/admin/sessions/{session_id}")
async def admin_get_session(
    session_id: str,
    admin_token: str = Header(..., alias="admin-token"),
):
    """Get full session with messages and reasoning traces."""
    verify_admin_token(admin_token)
    if not session_store:
        raise HTTPException(status_code=503, detail="Session store unavailable")
    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/admin/sessions/{session_id}/rating")
async def admin_rate_session(
    session_id: str,
    request: SessionRatingRequest,
    admin_token: str = Header(..., alias="admin-token"),
):
    """Admin rates a session for quality tracking."""
    verify_admin_token(admin_token)
    if not session_store:
        raise HTTPException(status_code=503, detail="Session store unavailable")
    await session_store.add_rating(session_id, request.rating, request.note)
    return {"status": "ok", "session_id": session_id, "rating": request.rating}

@app.post("/v1/chat/completions")
async def chat_completion_endpoint(
    request: ChatRequest,
    user_id: str = Header(default="anonymous", alias="x-user-id"),
    openclaw_session: Optional[str] = Header(None, alias="X-OpenClaw-Session"),
    openclaw_channel: Optional[str] = Header(None, alias="X-OpenClaw-Channel"),
    bbx_session: Optional[str] = Header(None, alias="X-BBX-Session"),
):
    """
    OpenAI-compatible endpoint supporting both standard and CopilotKit formats.
    Handles both 'messages' (OpenAI) and 'input' (CopilotKit) fields.
    Supports both streaming and non-streaming responses.

    Now includes full observability instrumentation.
    """
    # If streaming is requested, use the streaming handler
    if request.stream:
        session_id_override: Optional[str] = None
        if openclaw_session:
            session_id_override = f"oc-{openclaw_session}"
        elif request.thread_id:
            session_id_override = request.thread_id
        elif bbx_session:
            session_id_override = f"ui-{bbx_session}"
        return await chat_completion_stream(request, session_id_override=session_id_override)

    # ==========================================================
    # Observability Setup
    # ==========================================================

    start_time = time.time()
    request_start_ms = int(start_time * 1000)
    
    # OpenClaw session bridging: use prefixed session ID when OpenClaw headers present
    if openclaw_session:
        session_id = f"oc-{openclaw_session}"
        channel = openclaw_channel or "openclaw"
        if session_store:
            await session_store.ensure_session(session_id, openclaw_session, channel)
        logger.info(f"Bridged OpenClaw session: {openclaw_session} -> {session_id} (channel: {channel})")
    else:
        if request.thread_id:
            session_id = request.thread_id
        elif bbx_session:
            session_id = f"ui-{bbx_session}"
        else:
            session_id = str(uuid.uuid4())

    # Get current trace context (for linking to Jaeger)
    current_span = trace.get_current_span() if OPENTELEMETRY_AVAILABLE else None
    trace_id = format(current_span.get_span_context().trace_id, '032x') if current_span else "no-trace"

    # Track active sessions
    if PROMETHEUS_AVAILABLE:
        active_sessions.inc()

    # Debug logging
    try:
        logger.info(f"Incoming Request: {request.model_dump_json(exclude={'input'})}")
    except:
        pass

    # Normalize input to messages format
    messages_to_process = []

    if request.messages:
        # Standard OpenAI format
        messages_to_process = request.messages
    elif request.input:
        # CopilotKit format - convert input array to messages
        for item in request.input:
            if isinstance(item, dict) and "role" in item:
                content = item.get("content", "")
                msg = ChatMessage(role=item["role"], content=content)
                if "tool_calls" in item:
                    msg.tool_calls = item["tool_calls"]
                messages_to_process.append(msg)
    else:
        if PROMETHEUS_AVAILABLE:
            active_sessions.dec()
        raise HTTPException(status_code=422, detail="Either 'messages' or 'input' field is required")

    # Extract user message for logging
    user_message = ""
    for msg in messages_to_process:
        if msg.role == "user":
            user_message = parse_message_content(msg.content) if msg.content is not None else ""

    # Convert to LangChain messages
    lc_messages = []
    for msg in messages_to_process:
        content_text = parse_message_content(msg.content) if msg.content is not None else ""

        if msg.role == "user":
            lc_messages.append(HumanMessage(content=content_text))
        elif msg.role == "assistant":
            # Handle tool calls in history
            tool_calls = msg.tool_calls or []
            lc_messages.append(AIMessage(content=content_text, tool_calls=tool_calls))
        elif msg.role == "system":
            lc_messages.append(SystemMessage(content=content_text))
        elif msg.role == "tool":
            # Handle tool outputs if needed, but for now we skip complex reconstruction
            pass

    if not lc_messages:
        if PROMETHEUS_AVAILABLE:
            active_sessions.dec()
        raise HTTPException(status_code=422, detail="No valid messages to process")

    # Extract optimization metadata from request
    force_domain = None
    query_type = None
    if request.metadata:
        force_domain = request.metadata.get("force_domain")
        query_type = request.metadata.get("query_type")  # count, semantic, hybrid
        if force_domain:
            logger.info(f"force_domain={force_domain} from metadata (skipping router LLM)")

    inputs: AgentState = {
        "messages": lc_messages,
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {
            "force_domain": force_domain,
            "query_type": query_type,
        },
        "plan": [],
        "step": 0
    }

    logger.info(f"Processing request with {len(lc_messages)} messages")

    try:
        # ==========================================================
        # Agent Execution (with instrumentation)
        # ==========================================================

        token = BESTBOX_TOOL_RESULTS_SESSION_ID.set(session_id)
        try:
            result = await agent_app.ainvoke(cast(AgentState, inputs))
        finally:
            BESTBOX_TOOL_RESULTS_SESSION_ID.reset(token)

        last_msg = result["messages"][-1]
        current_agent = result.get("current_agent", "unknown")
        confidence = result.get("confidence", 0.0)

        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        tool_calls = last_msg.tool_calls if hasattr(last_msg, 'tool_calls') else None

        # ==========================================================
        # OPTION A: Get full tool results from global cache
        # Don't clear - let frontend fetch via /v1/tool-results/latest
        # ==========================================================
        try:
            from tools.troubleshooting_tools import get_latest_full_results
            full_tool_results = get_latest_full_results(session_id=session_id, after_ms=request_start_ms - 1)
            # Don't clear - frontend will fetch separately
        except ImportError:
            full_tool_results = None

        # Ensure content is a string
        if content is None:
            content = ""

        # Embed full tool results for the UI (frontend extracts and renders).
        if full_tool_results:
            tool_results_json = json.dumps([full_tool_results], ensure_ascii=False)
            content = f"[TOOL_RESULTS]{tool_results_json}[/TOOL_RESULTS]\n\n{content}"

        # Include session id for deterministic frontend fetch fallback.
        content = f"{content}\n\n[BBX_SESSION]{session_id}[/BBX_SESSION]"

        # ==========================================================
        # Validate response - filter hallucinated case_ids
        # ==========================================================
        if VALIDATOR_AVAILABLE and content and current_agent == "mold_agent":
            try:
                original_content = content
                content = validate_and_filter_results(content)
                if content != original_content:
                    logger.info("Filtered hallucinated case_ids from mold_agent response")
            except Exception as e:
                logger.warning(f"Response validation failed: {e}")

        # ==========================================================
        # Observability Tracking
        # ==========================================================

        # Calculate latency
        latency_seconds = time.time() - start_time
        latency_ms = int(latency_seconds * 1000)

        if PROMETHEUS_AVAILABLE:
            # Track request
            agent_requests.labels(
                agent_type=current_agent,
                user_id=user_id
            ).inc()

            # Track latency
            agent_latency.labels(
                agent_type=current_agent
            ).observe(latency_seconds)

            # Track tool executions (if any tool calls were made)
            if tool_calls:
                for tool_call in (tool_calls if isinstance(tool_calls, list) else [tool_calls]):
                    tool_name = tool_call.get('name', 'unknown') if isinstance(tool_call, dict) else 'unknown'
                    tool_execution_success.labels(
                        tool_name=tool_name,
                        status="success"
                    ).inc()

        # Log conversation to PostgreSQL
        await log_conversation(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            agent_response=content or "",
            agent_type=current_agent,
            tool_calls=tool_calls if tool_calls else [],
            latency_ms=latency_ms,
            confidence=confidence,
            trace_id=trace_id
        )

        # Build message dict
        message_dict = {
            "role": "assistant",
            "content": content or ""  # Ensure empty string if None, unless tool_calls
        }

        if tool_calls:
            message_dict["tool_calls"] = tool_calls
            if not content:
                message_dict["content"] = None

        # Return OpenAI-compatible response format
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model or "bestbox-agent",
            "choices": [
                {
                    "index": 0,
                    "message": message_dict,
                    "finish_reason": "tool_calls" if tool_calls else "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "agent": current_agent,
            "session_id": session_id  # Include session_id for feedback tracking
        }

        logger.info(f"Returning response from agent: {current_agent} (latency: {latency_ms}ms)")
        return response

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")

        # Track error
        if PROMETHEUS_AVAILABLE:
            tool_execution_success.labels(
                tool_name="agent_execution",
                status="error"
            ).inc()

        # Log error to database
        latency_ms = int((time.time() - start_time) * 1000)
        await log_conversation(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            agent_response=f"ERROR: {str(e)}",
            agent_type="error",
            tool_calls=[],
            latency_ms=latency_ms,
            confidence=0.0,
            trace_id=trace_id
        )

        # Return a polite error message instead of 500 crashes
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model or "bestbox-agent",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"I encountered an error processing your request: {str(e)}",
                },
                "finish_reason": "stop"
            }],
            "session_id": session_id
        }

    finally:
        # Always decrement active sessions
        if PROMETHEUS_AVAILABLE:
            active_sessions.dec()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AGENT_API_PORT", "8000")))  # Bind to all interfaces for Docker access
