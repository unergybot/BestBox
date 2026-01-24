"""
Speech-to-Speech WebSocket Gateway for BestBox

Provides real-time S2S interaction by connecting:
- ASR (faster-whisper) for speech recognition
- LangGraph agents for reasoning and tool use
- TTS (XTTS v2) for speech synthesis

Protocol:
- Client → Server: Binary (PCM16 audio) or JSON control messages
- Server → Client: JSON (transcripts, tokens) or Binary (audio)
"""

import asyncio
import json
import uuid
import numpy as np
import logging
import time
import sys
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.speech.asr import StreamingASR, ASRConfig, ASRPool
from services.speech.tts import StreamingTTS, TTSConfig, SpeechBuffer

# Conditional imports for LangGraph integration
try:
    from agents.graph import app as agent_app
    from agents.state import AgentState
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    agent_app = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class S2SConfig:
    """Configuration for S2S gateway."""
    host: str = "0.0.0.0"
    port: int = 8765
    
    # ASR config
    asr_model: str = "large-v3"
    asr_device: str = "cuda"
    asr_language: str = "zh"
    
    # TTS config
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_gpu: bool = True
    tts_language: str = "zh-cn"
    
    # Session config
    max_sessions: int = 10
    session_timeout: int = 300  # seconds
    max_audio_buffer: int = 30 * 16000 * 2  # 30 seconds PCM16
    
    # Speech buffer config
    min_phrase_chars: int = 30
    max_phrase_chars: int = 200


# Load config from environment
def load_config() -> S2SConfig:
    return S2SConfig(
        host=os.environ.get("S2S_HOST", "0.0.0.0"),
        port=int(os.environ.get("S2S_PORT", "8765")),
        asr_model=os.environ.get("ASR_MODEL", "large-v3"),
        asr_device=os.environ.get("ASR_DEVICE", "cuda"),
        asr_language=os.environ.get("ASR_LANGUAGE", "zh"),
        tts_model=os.environ.get("TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2"),
        tts_gpu=os.environ.get("TTS_GPU", "true").lower() == "true",
        tts_language=os.environ.get("TTS_LANGUAGE", "zh-cn"),
    )


# ==============================================================================
# Session Management
# ==============================================================================

@dataclass
class S2SSession:
    """Per-connection session state."""
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    # Components
    asr: Optional[StreamingASR] = None
    speech_buffer: Optional[SpeechBuffer] = None
    
    # Conversation state
    messages: List[Dict[str, str]] = field(default_factory=list)
    current_response: str = ""
    is_speaking: bool = False
    
    # Settings
    language: str = "zh"
    
    def touch(self):
        """Update last activity time."""
        self.last_activity = time.time()
    
    def add_user_message(self, text: str):
        """Add user message to history."""
        self.messages.append({"role": "user", "content": text})
        self.touch()
    
    def add_assistant_message(self, text: str):
        """Add assistant message to history."""
        self.messages.append({"role": "assistant", "content": text})
        self.touch()
    
    def get_langchain_messages(self):
        """Convert to LangChain message format."""
        lc_messages = []
        for msg in self.messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        return lc_messages


class SessionManager:
    """Manage S2S sessions with cleanup."""
    
    def __init__(self, config: S2SConfig):
        self.config = config
        self.sessions: Dict[str, S2SSession] = {}
        self.asr_pool = ASRPool(
            ASRConfig(
                model_size=config.asr_model,
                device=config.asr_device,
                language=config.asr_language
            ),
            max_sessions=config.max_sessions
        )
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def create_session(self) -> S2SSession:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        
        session = S2SSession(
            session_id=session_id,
            asr=self.asr_pool.get_session(session_id),
            speech_buffer=SpeechBuffer(
                min_chars=self.config.min_phrase_chars,
                max_chars=self.config.max_phrase_chars
            )
        )
        
        self.sessions[session_id] = session
        logger.info(f"Session created: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[S2SSession]:
        """Get existing session."""
        session = self.sessions.get(session_id)
        if session:
            session.touch()
        return session
    
    def remove_session(self, session_id: str):
        """Remove a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.asr_pool.remove_session(session_id)
            logger.info(f"Session removed: {session_id}")
    
    async def cleanup_expired(self):
        """Remove expired sessions."""
        now = time.time()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session.last_activity > self.config.session_timeout
        ]
        for sid in expired:
            self.remove_session(sid)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
    
    async def start_cleanup_task(self):
        """Start background cleanup task."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)  # Check every minute
                await self.cleanup_expired()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    def stop_cleanup_task(self):
        """Stop cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()


# ==============================================================================
# FastAPI Application
# ==============================================================================

# Global state
config: S2SConfig = None
session_manager: SessionManager = None
tts_model: Optional[StreamingTTS] = None
tts_loading: bool = False
tts_lock = asyncio.Lock()


async def get_tts_model() -> Optional[StreamingTTS]:
    """Lazy-load TTS model on first request."""
    global tts_model, tts_loading
    
    # Check if disabled
    if os.environ.get("S2S_ENABLE_TTS", "false").lower() != "true":
        return None

    if tts_model is not None:
        return tts_model

    async with tts_lock:
        # Double-check pattern
        if tts_model is not None:
            return tts_model
            
        try:
            logger.info("Loading TTS model (lazy)...")
            tts_model = StreamingTTS(TTSConfig(
                model_name=config.tts_model,
                gpu=config.tts_gpu,
                default_language=config.tts_language
            ))
            logger.info("TTS model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            return None
            
    return tts_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global config, session_manager
    
    # Startup
    logger.info("Starting S2S Gateway...")
    config = load_config()
    session_manager = SessionManager(config)
    
    # NOTE: TTS model is now lazy-loaded in get_tts_model()
    # to prevent blocking startup if it takes too long or hangs
    
    # Start cleanup task
    await session_manager.start_cleanup_task()
    
    logger.info(f"S2S Gateway ready on ws://{config.host}:{config.port}/ws/s2s")
    
    yield
    
    # Shutdown
    logger.info("Shutting down S2S Gateway...")
    session_manager.stop_cleanup_task()
    session_manager.asr_pool.cleanup()


app = FastAPI(
    title="BestBox S2S Gateway",
    description="Speech-to-Speech WebSocket gateway with LangGraph integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# REST Endpoints
# ==============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "s2s-gateway",
        "sessions": len(session_manager.sessions) if session_manager else 0,
        "langgraph_available": LANGGRAPH_AVAILABLE,
        "tts_enabled": os.environ.get("S2S_ENABLE_TTS", "false").lower() == "true",
        "tts_loaded": tts_model is not None
    }


@app.get("/info")
async def info():
    """Service information."""
    return {
        "service": "BestBox S2S Gateway",
        "version": "1.0.0",
        "asr_model": config.asr_model if config else "not loaded",
        "tts_model": config.tts_model if config else "not loaded",
        "max_sessions": config.max_sessions if config else 0,
        "langgraph_available": LANGGRAPH_AVAILABLE,
        "tts_status": "loaded" if tts_model else "lazy-waiting"
    }


class SynthesizeRequest(BaseModel):
    text: str
    language: Optional[str] = None


@app.post("/api/synthesize")
async def synthesize(request: SynthesizeRequest):
    """Synthesize text to speech (REST endpoint for testing)."""
    model = await get_tts_model()
    
    if not model:
        raise HTTPException(status_code=503, detail="TTS not available (disabled or failed to load)")
    
    audio = model.synthesize(
        request.text,
        language=request.language or config.tts_language
    )
    
    return {
        "audio_base64": audio.hex() if audio else "",
        "sample_rate": model.sample_rate,
        "format": "pcm16"
    }


# ==============================================================================
# WebSocket S2S Endpoint
# ==============================================================================

@app.websocket("/ws/s2s")
async def speech_to_speech(ws: WebSocket):
    """
    Main S2S WebSocket endpoint.
    
    Protocol:
    
    Client → Server:
    - Binary: PCM16 audio chunks (16kHz, mono)
    - JSON: Control messages
        - {"type": "session_start", "lang": "zh"}
        - {"type": "audio_end"}
        - {"type": "interrupt"}
        - {"type": "text_input", "text": "..."}  # Text-only mode
    
    Server → Client:
    - JSON: Status and text
        - {"type": "asr_partial", "text": "..."}
        - {"type": "asr_final", "text": "..."}
        - {"type": "llm_token", "token": "..."}
        - {"type": "response_end"}
        - {"type": "error", "message": "..."}
    - Binary: PCM16 audio chunks (24kHz, mono)
    """
    await ws.accept()
    
    # Create session
    session = session_manager.create_session()
    logger.info(f"WebSocket connected: {session.session_id}")
    
    try:
        while True:
            message = await ws.receive()
            
            # Binary audio data
            if "bytes" in message:
                await handle_audio(ws, session, message["bytes"])
            
            # JSON control messages
            elif "text" in message:
                data = json.loads(message["text"])
                await handle_control(ws, session, data)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session.session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await ws.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass
    finally:
        session_manager.remove_session(session.session_id)


async def handle_audio(ws: WebSocket, session: S2SSession, audio_bytes: bytes):
    """Handle incoming audio chunk."""
    # Debug logging to verify audio flow
    if not hasattr(session, "_packets"): session._packets = 0
    session._packets += 1
    if session._packets % 50 == 0:  # Log every 50 packets (~1 sec)
        logger.info(f"Session {session.session_id} received {session._packets} packets. Last chunk: {len(audio_bytes)} bytes")

    # Convert to numpy
    pcm = np.frombuffer(audio_bytes, dtype=np.int16)
    
    # Feed to ASR (run in thread to avoid blocking event loop)
    # openai-whisper is synchronous and can block for seconds
    result = await asyncio.to_thread(session.asr.feed_audio, pcm)
    
    # Send partial if available
    if result and result["type"] == "partial":
        await ws.send_text(json.dumps({
            "type": "asr_partial",
            "text": result["text"]
        }))


async def handle_control(ws: WebSocket, session: S2SSession, data: Dict[str, Any]):
    """Handle control message."""
    msg_type = data.get("type")
    
    if msg_type == "session_start":
        # Initialize/reset session
        lang = data.get("lang", "zh")
        session.language = lang
        session.asr.reset()
        session.asr.set_language(lang)
        session.speech_buffer.clear()
        # Pre-warm TTS if enabled (fire and forget)
        asyncio.create_task(get_tts_model())
        logger.info(f"Session {session.session_id} started with lang={lang}")
        
        await ws.send_text(json.dumps({
            "type": "session_ready",
            "session_id": session.session_id
        }))
    
    elif msg_type == "audio_end":
        # Finalize ASR and run agent
        # Run finalize in thread to prevent blocking
        final = await asyncio.to_thread(session.asr.finalize)
        text = final["text"].strip()
        
        if text:
            await ws.send_text(json.dumps({
                "type": "asr_final",
                "text": text
            }))
            
            # Run agent in background
            asyncio.create_task(
                run_agent_and_speak(ws, session, text)
            )
        else:
            await ws.send_text(json.dumps({
                "type": "asr_final",
                "text": ""
            }))
    
    elif msg_type == "text_input":
        # Direct text input (skip ASR)
        text = data.get("text", "").strip()
        if text:
            asyncio.create_task(
                run_agent_and_speak(ws, session, text)
            )
    
    elif msg_type == "interrupt":
        # User interrupted - stop TTS
        session.speech_buffer.clear()
        session.asr.reset()
        session.is_speaking = False
        logger.info(f"Session {session.session_id} interrupted")
        
        await ws.send_text(json.dumps({
            "type": "interrupted"
        }))
    
    else:
        logger.warning(f"Unknown message type: {msg_type}")


async def run_agent_and_speak(ws: WebSocket, session: S2SSession, user_text: str):
    """Run LangGraph agent and stream response as speech."""
    
    session.is_speaking = True
    session.current_response = ""
    session.add_user_message(user_text)
    
    try:
        # Ensure TTS is loaded (or loading)
        model = await get_tts_model()
        
        if LANGGRAPH_AVAILABLE and agent_app is not None:
            await _run_langgraph_agent(ws, session, user_text, model)
        else:
            # Fallback: echo mode for testing
            await _run_echo_mode(ws, session, user_text, model)
        
    except Exception as e:
        logger.error(f"Agent error: {e}")
        await ws.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
    finally:
        session.is_speaking = False


async def _run_langgraph_agent(ws: WebSocket, session: S2SSession, user_text: str, tts_model: Optional[StreamingTTS]):
    """Run LangGraph agent with streaming."""
    # Build inputs
    inputs: AgentState = {
        "messages": session.get_langchain_messages(),
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {},
        "plan": [],
        "step": 0
    }
    
    full_response = ""
    
    # Stream agent response
    async for event in agent_app.astream_events(inputs, version="v2"):
        if not session.is_speaking:
            # Interrupted
            break
        
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                token = chunk.content
                full_response += token
                
                # Send token to client
                await ws.send_text(json.dumps({
                    "type": "llm_token",
                    "token": token
                }))
                
                # Check if ready to speak
                phrase = session.speech_buffer.add(token)
                if phrase and tts_model:
                    audio = tts_model.synthesize(phrase, language=session.language)
                    if audio:
                        await ws.send_bytes(audio)
    
    # Flush remaining text
    if session.is_speaking:
        remaining = session.speech_buffer.flush()
        if remaining and tts_model:
            audio = tts_model.synthesize(remaining, language=session.language)
            if audio:
                await ws.send_bytes(audio)
    
    # Update history
    if full_response:
        session.add_assistant_message(full_response)
    
    await ws.send_text(json.dumps({"type": "response_end"}))


async def _run_echo_mode(ws: WebSocket, session: S2SSession, user_text: str, tts_model: Optional[StreamingTTS]):
    """Echo mode for testing without LangGraph."""
    response = f"我收到了你的消息：{user_text}"
    
    # Stream tokens (simulate)
    for char in response:
        if not session.is_speaking:
            break
        
        await ws.send_text(json.dumps({
            "type": "llm_token",
            "token": char
        }))
        
        phrase = session.speech_buffer.add(char)
        if phrase and tts_model:
            audio = tts_model.synthesize(phrase, language=session.language)
            if audio:
                await ws.send_bytes(audio)
        
        await asyncio.sleep(0.02)  # Simulate typing
    
    # Flush remaining
    if session.is_speaking:
        remaining = session.speech_buffer.flush()
        if remaining and tts_model:
            audio = tts_model.synthesize(remaining, language=session.language)
            if audio:
                await ws.send_bytes(audio)
    
    session.add_assistant_message(response)
    await ws.send_text(json.dumps({"type": "response_end"}))


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    """Run the S2S gateway server."""
    import uvicorn
    
    config = load_config()
    
    uvicorn.run(
        "services.speech.s2s_server:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
