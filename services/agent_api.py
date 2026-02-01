import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# OpenTelemetry imports - MUST be before other imports for auto-instrumentation
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
try:
    from openinference.instrumentation.langchain import LangChainInstrumentor
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
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

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union, cast
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agents.graph import app as agent_app
from agents.state import AgentState
import uvicorn
import json
import time
import uuid
import asyncpg

# Prometheus metrics
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from observability import (
        agent_requests,
        agent_latency,
        llm_tokens_generated,
        tool_execution_success,
        user_satisfaction,
        active_sessions
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("⚠️  Prometheus metrics not available. Install with: pip install prometheus-client")

app = FastAPI(title="BestBox Agent API")

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

@app.on_event("startup")
async def startup():
    """Initialize database connection pool and register plugin HTTP routes on startup"""
    global db_pool

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

    # Initialize database connection pool
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
        logger.info("✅ Database connection pool initialized")
    except Exception as e:
        logger.warning(f"⚠️  Database connection failed: {e}. Observability logging will be disabled.")
        db_pool = None

@app.on_event("shutdown")
async def shutdown():
    """Close database connection pool on shutdown"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")

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

class ChatResponse(BaseModel):
    response: str
    agent: str
    trace: List[Dict[str, Any]] = []

@app.get("/health")
async def health():
    return {"status": "ok", "service": "langgraph-agent"}

@app.get("/api/troubleshooting/images/{image_id}")
async def get_troubleshooting_image(image_id: str):
    """
    Serve troubleshooting case images.
    Images are stored in data/troubleshooting/processed/images/
    """
    import os
    from fastapi.responses import FileResponse

    # Sanitize image_id to prevent directory traversal
    if '..' in image_id or '/' in image_id:
        raise HTTPException(status_code=400, detail="Invalid image ID")

    image_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "troubleshooting", "processed", "images", image_id
    )

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(image_path, media_type="image/jpeg")

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

async def ag_ui_stream(request: ChatRequest):
    """
    Stream the response using AG-UI protocol (CopilotKit v1.51+).
    Events: TEXT_MESSAGE_START -> TEXT_MESSAGE_CONTENT -> TEXT_MESSAGE_END -> RUN_FINISHED
    """
    async def generate():
        try:
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
                error_event = {"type": "RUN_ERROR", "message": "No messages provided", "code": "invalid_request"}
                yield f"data: {json.dumps(error_event)}\n\n"
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

            inputs: AgentState = {
                "messages": lc_messages,
                "current_agent": "router",
                "tool_calls": 0,
                "confidence": 1.0,
                "context": {},
                "plan": [],
                "step": 0
            }

            # Generate unique IDs for this response
            message_id = f"msg_{uuid.uuid4().hex[:24]}"

            # Get response from agent with recursion limit
            result = await agent_app.ainvoke(
                cast(AgentState, inputs),
                config={"recursion_limit": 50}
            )
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            tool_calls_result = last_msg.tool_calls if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls else None

            # Ensure content is never None
            if content is None:
                content = ""

            # Always emit text content if it exists (even when there are also tool calls)
            # This handles the case where tool call limit is reached but there's still content
            if content.strip():
                # TEXT_MESSAGE_START
                yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_START', 'messageId': message_id, 'role': 'assistant'})}\n\n"

                # Stream content as TEXT_MESSAGE_CONTENT events
                chunk_size = 50
                for i in range(0, len(content), chunk_size):
                    chunk_text = content[i:i + chunk_size]
                    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': message_id, 'delta': chunk_text})}\n\n"

                # TEXT_MESSAGE_END
                yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_END', 'messageId': message_id})}\n\n"

            # Also emit tool calls if present (CopilotKit may need to handle them)
            if tool_calls_result:
                for tool_call in tool_calls_result:
                    tool_call_id = f"call_{uuid.uuid4().hex[:24]}"
                    tool_name = tool_call.get("name", "unknown") if isinstance(tool_call, dict) else getattr(tool_call, 'name', 'unknown')
                    tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})

                    # TOOL_CALL_START
                    yield f"data: {json.dumps({'type': 'TOOL_CALL_START', 'toolCallId': tool_call_id, 'toolCallName': tool_name})}\n\n"

                    # TOOL_CALL_ARGS
                    yield f"data: {json.dumps({'type': 'TOOL_CALL_ARGS', 'toolCallId': tool_call_id, 'delta': json.dumps(tool_args)})}\n\n"

                    # TOOL_CALL_END
                    yield f"data: {json.dumps({'type': 'TOOL_CALL_END', 'toolCallId': tool_call_id})}\n\n"

            # RUN_FINISHED - Terminal event (REQUIRED!)
            yield f"data: {json.dumps({'type': 'RUN_FINISHED'})}\n\n"

        except Exception as e:
            logger.error(f"AG-UI streaming error: {e}")
            # RUN_ERROR - Terminal event for errors (REQUIRED!)
            error_event = {"type": "RUN_ERROR", "message": str(e), "code": "internal_error"}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/responses")
async def create_response_v0(request: ChatRequest):
    """
    CopilotKit AG-UI protocol endpoint (without /v1 prefix).
    Uses AG-UI streaming format with TEXT_MESSAGE_* and RUN_FINISHED events.
    """
    if request.stream:
        return await ag_ui_stream(request)
    else:
        return await chat_completion(request)


@app.post("/v1/responses")
async def create_response(request: ChatRequest):
    """
    CopilotKit AG-UI protocol endpoint.
    Uses AG-UI streaming format with TEXT_MESSAGE_* and RUN_FINISHED events.
    """
    if request.stream:
        return await ag_ui_stream(request)
    else:
        return await chat_completion(request)

async def chat_completion_stream(request: ChatRequest):
    """Stream the response using SSE format"""
    async def generate():
        try:
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
            
            inputs: AgentState = {
                "messages": lc_messages,
                "current_agent": "router",
                "tool_calls": 0,
                "confidence": 1.0,
                "context": {},
                "plan": [],
                "step": 0
            }
            
            # Get response from agent with recursion limit to prevent infinite loops
            # Primary protection is tool_calls counter (max 5), this is a safety net
            result = await agent_app.ainvoke(
                cast(AgentState, inputs),
                config={"recursion_limit": 50}
            )
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            tool_calls = last_msg.tool_calls if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls else None
            
            # Ensure content is never undefined - always a string (unless tool calls only)
            if content is None:
                content = ""
            
            response_id = f"chatcmpl-{int(time.time())}"
            created_time = int(time.time())
            model_name = request.model or "bestbox-agent"

            # Always stream content first if it exists (even when there are also tool_calls)
            # This handles the case where tool call limit is reached but there's still content
            if content.strip():
                chunk_size = 50
                for i in range(0, len(content), chunk_size):
                    chunk_text = content[i:i + chunk_size]
                    chunk_data = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": chunk_text},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"

            # Then emit tool calls if present
            if tool_calls:
                chunk_data = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": tool_calls
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"

            # Final chunk with finish_reason
            final_chunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls" if tool_calls else "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
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


async def chat_completion(request: ChatRequest) -> Dict[str, Any]:
    """
    Non-streaming chat completion handler.
    Core logic shared by /responses and /v1/chat/completions endpoints.
    """
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
    for msg in messages_to_process:
        content_text = parse_message_content(msg.content) if msg.content is not None else ""

        if msg.role == "user":
            lc_messages.append(HumanMessage(content=content_text))
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
        "step": 0
    }

    # Set recursion limit to prevent infinite loops (safety net for tool_calls counter)
    result = await agent_app.ainvoke(
        cast(AgentState, inputs),
        config={"recursion_limit": 50}
    )

    last_msg = result["messages"][-1]
    current_agent = result.get("current_agent", "unknown")

    content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    tool_calls = last_msg.tool_calls if hasattr(last_msg, 'tool_calls') else None

    message_dict = {
        "role": "assistant",
        "content": content or ""
    }

    if tool_calls:
        message_dict["tool_calls"] = tool_calls
        if not content:
            message_dict["content"] = None

    return {
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
        "agent": current_agent
    }


def parse_message_content(content: Union[str, List[Dict[str, Any]]]) -> str:
    """Parse message content from either string or array format"""
    if isinstance(content, str):
        return content
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

@app.post("/v1/chat/completions")
async def chat_completion_endpoint(
    request: ChatRequest,
    user_id: str = Header(default="anonymous", alias="x-user-id")
):
    """
    OpenAI-compatible endpoint supporting both standard and CopilotKit formats.
    Handles both 'messages' (OpenAI) and 'input' (CopilotKit) fields.
    Supports both streaming and non-streaming responses.

    Now includes full observability instrumentation.
    """
    # If streaming is requested, use the streaming handler
    if request.stream:
        return await chat_completion_stream(request)

    # ==========================================================
    # Observability Setup
    # ==========================================================

    start_time = time.time()
    session_id = request.thread_id or str(uuid.uuid4())

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

    inputs: AgentState = {
        "messages": lc_messages,
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {},
        "plan": [],
        "step": 0
    }

    logger.info(f"Processing request with {len(lc_messages)} messages")

    try:
        # ==========================================================
        # Agent Execution (with instrumentation)
        # ==========================================================

        # Set recursion limit to prevent infinite loops (safety net for tool_calls counter)
        result = await agent_app.ainvoke(
            cast(AgentState, inputs),
            config={"recursion_limit": 50}
        )

        last_msg = result["messages"][-1]
        current_agent = result.get("current_agent", "unknown")
        confidence = result.get("confidence", 0.0)

        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        tool_calls = last_msg.tool_calls if hasattr(last_msg, 'tool_calls') else None

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
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Bind to all interfaces for Docker access
