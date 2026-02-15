"""
BestBox LiveKit Voice Agent

Integrates BestBox LangGraph agents with LiveKit for real-time voice interaction.
Provides significant latency improvements over custom WebSocket implementation.

Requirements:
    pip install "livekit-agents[silero,langchain,turn-detector]~=1.0"
    pip install livekit-plugins-openai

Usage:
    # Start LiveKit server first
    livekit-server --dev

    # Then run this agent
    python services/livekit_agent.py dev

Environment Variables:
    LIVEKIT_URL: LiveKit server URL (default: ws://localhost:7880)
    LIVEKIT_API_KEY: API key (auto-generated in dev mode)
    LIVEKIT_API_SECRET: API secret (auto-generated in dev mode)
    OPENAI_BASE_URL: For local LLM (default: http://localhost:8080/v1)
"""

import logging
import os
import sys
import re
import asyncio
import gc
import psutil
import time
import json


# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        # logging.StreamHandler(sys.stdout), # DISABLED to prevent IPC corruption
        logging.FileHandler("agent_debug.log", mode='a')
    ]
)
logger = logging.getLogger("bestbox-voice")

# Check for required packages
try:
    from livekit.agents import (
        AgentServer,
        AgentSession,
        JobContext,
        JobProcess,
        JobRequest,
        RunContext,
        WorkerOptions,
        cli,
        inference,
        metrics,
        MetricsCollectedEvent,
    )
    from livekit.agents.voice import Agent
    from livekit.agents.llm import function_tool
    from livekit.plugins import silero
    LIVEKIT_AVAILABLE = True
except ImportError as e:
    logger.error(f"LiveKit agents not installed: {e}")
    logger.error("Install with: pip install 'livekit-agents[silero,langchain,turn-detector]~=1.0'")
    LIVEKIT_AVAILABLE = False
    sys.exit(1)

# Try to load turn detector
try:
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    TURN_DETECTOR_AVAILABLE = True
except ImportError:
    logger.warning("Turn detector not available, using basic mode")
    TURN_DETECTOR_AVAILABLE = False
    MultilingualModel = None

# Try to load LangChain adapter for BestBox graph
try:
    from livekit.plugins import langchain as lk_langchain
    from agents.graph import app as bestbox_graph
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_core.runnables import RunnableLambda
    LANGGRAPH_INTEGRATION = True
    logger.info("BestBox LangGraph integration available")
except ImportError as e:
    logger.warning(f"LangGraph integration not available: {e}")
    LANGGRAPH_INTEGRATION = False
    bestbox_graph = None

# LangGraph integration enabled - real agent responses
ASR_BRIDGE_MODE = os.environ.get("ASR_BRIDGE_MODE", "false").lower() == "true"
if ASR_BRIDGE_MODE:
    logger.info("⚡ ASR BRIDGE MODE: ON (Transcripts to CopilotKit, LLM text responses, no TTS)")
# LANGGRAPH_INTEGRATION controlled by import success above
logger.info(f"🎯 LangGraph integration: {'ENABLED' if LANGGRAPH_INTEGRATION else 'DISABLED'}")

async def graph_wrapper(input_messages, **kwargs):
    """
    Wraps the LangGraph to:
    1. Accept list of messages (from LiveKit adapter)
    2. Convert to state dict
    3. Invoke graph (async)
    4. Extract final response content and clean it
    5. Return single AIMessage (not yield)

    Note: **kwargs added to handle 'context' and other parameters from LiveKit
    """
    import time
    from langchain_core.messages import AIMessage

    # DEBUG: Log what we received
    logger.info(f"🔍 GRAPH_WRAPPER: Received input_messages type={type(input_messages)}")
    logger.info(f"🔍 GRAPH_WRAPPER: input_messages={input_messages}")

    # Convert input messages to state
    # If input is already a dict, use it, otherwise wrap it
    if isinstance(input_messages, dict):
        state = input_messages
        messages_list = input_messages.get("messages", [])
    else:
        state = {"messages": input_messages}
        messages_list = input_messages

    # Extract user message for logging
    user_msg = ""
    if isinstance(messages_list, list) and len(messages_list) > 0:
        last = messages_list[-1]
        user_msg = last.content if hasattr(last, 'content') else str(last)
    else:
        logger.warning(f"⚠️ No messages in input! type={type(input_messages)}")

    start_time = time.perf_counter()
    logger.info(f"🎯 AGENT: Processing user input: '{user_msg[:100] if user_msg else '(empty)'}...'")
    logger.info(f"⏱️  TIMING: Agent processing started")

    try:
        # VOICE OPTIMIZATION: Skip router for simple queries to reduce latency
        # Pattern matching for common voice interactions
        simple_patterns = ["hello", "hi ", "thank", "help", "what can you", "who are you",
                           "你好", "谢谢", "帮助", "你是谁"]
        is_simple_query = any(pattern in user_msg.lower() for pattern in simple_patterns)

        if is_simple_query:
            # Fast path: Skip router, go directly to general_agent
            logger.info("⚡ FAST PATH: Bypassing router for simple query")
            from agents.general_agent import general_agent_node
            state["current_agent"] = "general_agent"
            output = general_agent_node(state)
        else:
            # Full path: Use complete graph with routing
            logger.info("🔄 FULL PATH: Using router for complex query")
            output = await bestbox_graph.ainvoke(state)

        duration = time.perf_counter() - start_time
        logger.info(f"✅ AGENT: Response generated in {duration*1000:.0f}ms")
        logger.info(f"⏱️  TIMING: Agent processing completed ({duration:.3f}s)")
        
        # Extract the final message
        messages = output.get("messages", [])
        if messages and len(messages) > 0:
            last_msg = messages[-1]
            if isinstance(last_msg, AIMessage):
                content = last_msg.content
            elif hasattr(last_msg, "content"):
                content = last_msg.content
            else:
                content = str(last_msg)
            
            logger.info(f"RAW_CONTENT: {content[:100]}...")
            
            # Clean content
            # 1. Remove JSON router output if present (specific to destination key)
            # Handle potential whitespace or newlines between keys
            content = re.sub(r'\{\s*"destination"\s*:.*?\}', '', content, flags=re.DOTALL)
            # Remove any other JSON-like blocks at start (e.g. generic reasoning)
            content = re.sub(r'^\s*\{.*?\}\s*', '', content, flags=re.DOTALL).strip()

            # 2. Extract [SPEECH] block if present (legacy format)
            speech_match = re.search(r'\[SPEECH\](.*?)\[/SPEECH\]', content, flags=re.DOTALL)
            if speech_match:
                cleaned_content = speech_match.group(1).strip()
                logger.info("PERF: Extracted [SPEECH] content")
            else:
                # 3. Parse [VOICE]/[TEXT] format for dual responses
                parsed = parse_dual_response(content)
                cleaned_content = parsed['voice']  # TTS speaks only VOICE portion
                logger.info(f"PERF: Parsed dual response - Voice: '{parsed['voice'][:50]}...'")

            print(f"DEBUG: graph_wrapper returning content: {cleaned_content[:50]}...", flush=True)
            logger.info(f"REQ_ID: extracted_content_len={len(cleaned_content)}")

            # Return single AIMessage with VOICE portion for TTS
            # The conversation_item_added handler will receive the full original content
            # and send TEXT portion via data channel
            return AIMessage(content=cleaned_content)
            
        logger.error(f"❌ AGENT: No response generated after {duration*1000:.0f}ms")
        return AIMessage(content="I'm sorry, I couldn't generate a response.")
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"❌ AGENT: Processing failed after {duration*1000:.0f}ms: {e}", exc_info=True)
        return AIMessage(content=f"System error: {str(e)}")

# ==============================================================================
# Local Adapters
# ==============================================================================
try:
    from services.livekit_local import LocalSTT, LocalTTS
    from services.speech.asr import ASRConfig
    from services.speech.tts import TTSConfig
    LOCAL_ADAPTERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Local adapters not available: {e}")
    LOCAL_ADAPTERS_AVAILABLE = False



# ==============================================================================
# Configuration
# ==============================================================================

# Local LLM configuration
LOCAL_LLM_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
LOCAL_LLM_MODEL = os.environ.get("LLM_MODEL", "Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf")

# STT/TTS configuration
# Set STT_MODEL=local or TTS_MODEL=local to force local processing
USE_LOCAL_SPEECH = os.environ.get("USE_LOCAL_SPEECH", "false").lower() == "true"
STT_MODEL = os.environ.get("STT_MODEL", "local" if USE_LOCAL_SPEECH else "deepgram/nova-3")
TTS_MODEL = os.environ.get("TTS_MODEL", "local" if USE_LOCAL_SPEECH else "cartesia/sonic-3")
TTS_VOICE = os.environ.get("TTS_VOICE", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc")

# Language configuration
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "multi")


# ==============================================================================
# Helper Functions
# ==============================================================================

def parse_dual_response(content: str) -> dict:
    """
    Extract VOICE and TEXT sections from agent response.

    Args:
        content: Agent response potentially containing [VOICE] and [TEXT] tags

    Returns:
        dict with 'voice', 'text', and 'full' keys
    """
    # Clean content - handle case where it's wrapped as string representation of list
    # e.g., "['[VOICE]...[/VOICE][TEXT]...[/TEXT]']"
    cleaned_content = str(content).strip()

    # Remove list wrapper if present
    if cleaned_content.startswith("['") and cleaned_content.endswith("']"):
        cleaned_content = cleaned_content[2:-2]
    elif cleaned_content.startswith('["') and cleaned_content.endswith('"]'):
        cleaned_content = cleaned_content[2:-2]

    # Unescape any escaped quotes
    cleaned_content = cleaned_content.replace("\\'", "'").replace('\\"', '"')

    voice_match = re.search(r'\[VOICE\](.*?)\[/VOICE\]', cleaned_content, re.DOTALL)
    text_match = re.search(r'\[TEXT\](.*?)\[/TEXT\]', cleaned_content, re.DOTALL)

    # Extract voice section or fallback to first 200 chars
    if voice_match:
        voice = voice_match.group(1).strip()
    else:
        # Fallback: use first sentence or 200 chars
        sentences = cleaned_content.split('. ')
        voice = sentences[0] if sentences else cleaned_content[:200]
        if not voice.endswith('.'):
            voice += '.'

    # Extract text section or use full content
    text = text_match.group(1).strip() if text_match else cleaned_content

    return {
        'voice': voice,
        'text': text,
        'full': content
    }


# ==============================================================================
# BestBox Voice Agent
# ==============================================================================

class BestBoxVoiceAgent(Agent):
    """
    Production-ready BestBox Voice Agent.
    
    Features:
    - Robust error handling and graceful degradation
    - Data channel support for real-time transcripts
    - Voice-optimized responses
    - Enterprise tool integration
    - Comprehensive logging and monitoring
    """

    def __init__(self, llm=None, tts=None):
        # NOTE: TTS MUST be passed to agent for the main loop to work!
        super().__init__(
            instructions=(
                "You are BestBox AI Assistant, a professional voice-enabled enterprise copilot. "
                "You specialize in ERP/Finance, CRM/Sales, IT Operations, and Office Automation.\n\n"
                "IMPORTANT: Structure your responses in this format:\n"
                "[VOICE]<concise 1-2 sentence answer suitable for speaking (under 30 words)>[/VOICE]\n"
                "[TEXT]<detailed explanation with full context and supporting information>[/TEXT]\n\n"
                "The VOICE section will be spoken aloud - keep it brief and conversational.\n"
                "The TEXT section will be displayed in chat - provide comprehensive details here.\n\n"
                "Example:\n"
                "[VOICE]We have 1,240 units in stock.[/VOICE]\n"
                "[TEXT]Current inventory shows 1,240 units total: 840 in main warehouse (Aisle A: 320 units, Aisle B: 520 units), and 400 in overflow storage. Stock levels are healthy for Q1 demand.[/TEXT]"
            ),
            llm=llm,
            tts=tts,
        )
        self._data_channel = None
        self._session_start_time = time.time()
        self._asr_bridge = ASR_BRIDGE_MODE
        logger.info(f"🎯 BestBoxVoiceAgent initialized with LLM={llm is not None}, TTS from session, ASR_BRIDGE={self._asr_bridge}")

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Called when user finishes speaking - process through LLM but skip TTS.
        
        Args:
            turn_ctx: The chat context for this turn
            new_message: The new message from the user
        """
        # Extract transcript from the new_message for logging
        transcript = new_message.content if hasattr(new_message, 'content') else str(new_message)
        if isinstance(transcript, list):
            transcript = " ".join(str(c) for c in transcript)
        logger.info(f"👤 User turn completed: '{str(transcript)[:100]}'")
        
        # DEBUG: Check if TTS is available to the agent
        tts_via_prop = self.tts
        logger.info(f"🔍 DEBUG: self.tts property resolves to: {tts_via_prop} (Type: {type(tts_via_prop)})")
        
        # DEBUG: Check session TTS directly
        if hasattr(self, '_session') and self._session:
             logger.info(f"🔍 DEBUG: self._session.tts resolves to: {self._session.tts} (Type: {type(self._session.tts)})")
        elif hasattr(self, 'session') and self.session:
             logger.info(f"🔍 DEBUG: self.session.tts resolves to: {self.session.tts} (Type: {type(self.session.tts)})")
        else:
             logger.info("🔍 DEBUG: Cannot access session from agent")
        
        logger.info("🤖 Agent will now generate response via LLM...")
        
        # Process through LLM to get text response, but skip TTS output
        # This sends the text response to CopilotKit message box without speaking
        if self._asr_bridge:
            logger.info("⚡ ASR BRIDGE MODE: Processing through LLM, skipping TTS output")
            # Generate response via LLM but don't speak it
            try:
                # Use the LLM directly to generate a response
                if self.llm:
                    from livekit.agents.llm import ChatContext, ChatMessage, ChatRole
                    
                    # Build chat context from turn_ctx
                    chat_ctx = ChatContext()
                    if hasattr(turn_ctx, 'messages') and turn_ctx.messages:
                        for msg in turn_ctx.messages:
                            chat_ctx.messages.append(msg)
                    
                    # Add the new user message
                    chat_ctx.messages.append(ChatMessage(role=ChatRole.USER, content=transcript))
                    
                    # Generate response
                    response_stream = self.llm.chat(chat_ctx=chat_ctx)
                    full_response = ""
                    async for chunk in response_stream:
                        if chunk and hasattr(chunk, 'content'):
                            full_response += chunk.content
                    
                    # Send text response to frontend via data channel
                    if full_response:
                        logger.info(f"🤖 LLM response (text only): '{full_response[:100]}...'")
                        await self.send_data_message("agent_response", full_response)
                        await self.send_data_message("agent_response_complete", "")
                else:
                    logger.warning("⚠️ No LLM available for text response generation")
            except Exception as e:
                logger.error(f"❌ Error generating text response: {e}", exc_info=True)
            return

        # Let parent class handle the actual response generation (with TTS)
        await super().on_user_turn_completed(turn_ctx, new_message)

    async def on_enter(self):
        """Called when agent joins the session - enhanced with data channels."""
        logger.info("🎯 BestBoxVoiceAgent entering session")
        
        # DEBUG: Inspect internal state
        if hasattr(self, '_activity') and self._activity:
            logger.info(f"🔍 DEBUG: Initial scheduling_paused={self._activity._scheduling_paused}")
        
        try:
            # Set up data channel for real-time communication
            await self._setup_data_channel()
            
            # Send agent ready signal
            await self.send_data_message("agent_ready", "BestBox Assistant connected and ready")
            
            # Voice greeting is handled by generate_greeting_audio() in entrypoint
            # which plays a musical beep sequence
            logger.info("🎯 Agent entering session - greeting handled by entrypoint")
                
            # FORCE UNPAUSE if needed
            if hasattr(self, '_activity') and self._activity:
                if self._activity._scheduling_paused:
                    logger.warning("⚠️ FORCE UNPAUSING agent scheduling...")
                    # Note: We use the internal method to unpause
                    async with self._activity._lock:
                        await self._activity._resume_scheduling_task()
                logger.info(f"🔍 DEBUG: Final scheduling_paused={self._activity._scheduling_paused}")
            
            logger.info("✅ BestBoxVoiceAgent session setup complete")
            
        except Exception as e:
            logger.error(f"❌ Agent on_enter failed: {e}", exc_info=True)
            # Continue anyway - basic functionality should still work

    async def _setup_data_channel(self):
        """Set up data channel for real-time communication with frontend."""
        try:
            # Wait for session to be fully ready
            if not hasattr(self, 'session') or self.session is None:
                logger.warning("⚠️ Session not ready for data channel, deferring setup")
                return

            if not hasattr(self.session, 'room') or self.session.room is None:
                logger.warning("⚠️ Room not ready for data channel, deferring setup")
                return

            # Send initial data to establish channel
            initial_data = {
                "type": "agent_status",
                "status": "initializing",
                "timestamp": time.time(),
                "session_id": f"bestbox-{int(time.time())}"
            }

            payload = json.dumps(initial_data).encode('utf-8')
            await self.session.room.local_participant.publish_data(
                payload=payload,
                reliable=True
            )

            self._data_channel = True
            logger.info("📡 Data channel established")

        except Exception as e:
            logger.error(f"❌ Data channel setup failed: {e}")
            self._data_channel = False

    async def send_data_message(self, message_type: str, text: str, metadata: dict = None):
        """Send structured data message to frontend."""
        if not self._data_channel:
            return
            
        try:
            message = {
                "type": message_type,
                "text": text,
                "timestamp": time.time(),
                "session_duration": time.time() - self._session_start_time
            }
            
            if metadata:
                message.update(metadata)
            
            payload = json.dumps(message).encode('utf-8')
            await self.session.room.local_participant.publish_data(
                payload=payload,
                reliable=True
            )
            
            logger.debug(f"📡 Data sent: {message_type} - {text[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Data send failed: {e}")

    async def on_user_speech_committed(self, user_msg: str):
        """Called when user speech is finalized."""
        logger.info(f"🎤 🔍 DEBUG: on_user_speech_committed called with: '{user_msg}'")
        logger.info(f"🎤 User: {user_msg}")
        
        # DEBUG: Verify LLM
        if self.llm:
             logger.info(f"🔍 DEBUG: self.llm is present: {type(self.llm)}")
        else:
             logger.error("❌ DEBUG: self.llm is NONE!")

        await self.send_data_message("user_transcript", user_msg)

    async def on_agent_speech_committed(self, agent_msg: str):
        """Called when agent speech is finalized."""
        logger.info(f"🔊 Agent: {agent_msg}")
        await self.send_data_message("agent_response", agent_msg)
        await self.send_data_message("agent_response_complete", "")

    # Enhanced tool definitions with better error handling
    @function_tool
    async def get_top_vendors(self, context: RunContext, limit: int = 5):
        """Get the top vendors by spend from ERP system.
        
        Args:
            limit: Number of top vendors to return (default: 5, max: 20)
        """
        logger.info(f"🔧 Tool: get_top_vendors(limit={limit})")
        
        try:
            # Validate input
            limit = max(1, min(limit, 20))  # Clamp between 1 and 20
            
            from tools.erp_tools import get_top_vendors as erp_get_top_vendors
            result = erp_get_top_vendors.invoke({"limit": limit})
            
            # Send tool result via data channel
            await self.send_data_message("tool_result", f"Retrieved top {limit} vendors", {
                "tool": "get_top_vendors",
                "result_count": len(result) if isinstance(result, list) else 1
            })
            
            return result
            
        except Exception as e:
            error_msg = f"Error retrieving vendor data: {str(e)}"
            logger.error(f"❌ Tool error: {error_msg}")
            await self.send_data_message("tool_error", error_msg, {"tool": "get_top_vendors"})
            return error_msg

    @function_tool
    async def get_inventory_levels(self, context: RunContext, warehouse: str = "all"):
        """Check current inventory levels across warehouses.
        
        Args:
            warehouse: Warehouse to check, or 'all' for all warehouses
        """
        logger.info(f"🔧 Tool: get_inventory_levels(warehouse={warehouse})")
        
        try:
            from tools.erp_tools import get_inventory_levels as erp_get_inventory
            result = erp_get_inventory.invoke({"warehouse": warehouse})
            
            await self.send_data_message("tool_result", f"Retrieved inventory for {warehouse}", {
                "tool": "get_inventory_levels",
                "warehouse": warehouse
            })
            
            return result
            
        except Exception as e:
            error_msg = f"Error retrieving inventory: {str(e)}"
            logger.error(f"❌ Tool error: {error_msg}")
            await self.send_data_message("tool_error", error_msg, {"tool": "get_inventory_levels"})
            return error_msg

    @function_tool
    async def get_customer_info(self, context: RunContext, customer_name: str):
        """Look up customer information from CRM system.
        
        Args:
            customer_name: Name of the customer to look up
        """
        logger.info(f"🔧 Tool: get_customer_info(customer={customer_name})")
        
        try:
            if not customer_name or len(customer_name.strip()) < 2:
                return "Please provide a valid customer name with at least 2 characters."
            
            from tools.crm_tools import get_customer_360
            result = get_customer_360.invoke({"customer_name": customer_name.strip()})
            
            await self.send_data_message("tool_result", f"Retrieved info for {customer_name}", {
                "tool": "get_customer_info",
                "customer": customer_name
            })
            
            return result
            
        except Exception as e:
            error_msg = f"Error retrieving customer data: {str(e)}"
            logger.error(f"❌ Tool error: {error_msg}")
            await self.send_data_message("tool_error", error_msg, {"tool": "get_customer_info"})
            return error_msg

    @function_tool
    async def search_knowledge_base(self, context: RunContext, query: str, domain: str = None):
        """Search company knowledge base for procedures, policies, or documentation.
        
        Args:
            query: Search query (minimum 3 characters)
            domain: Optional domain filter (erp, crm, it_ops, oa)
        """
        logger.info(f"🔧 Tool: search_knowledge_base(query='{query}', domain={domain})")
        
        try:
            if not query or len(query.strip()) < 3:
                return "Please provide a search query with at least 3 characters."
            
            # Validate domain
            valid_domains = ["erp", "crm", "it_ops", "oa", None]
            if domain and domain not in valid_domains:
                domain = None
            
            from tools.rag_tools import search_knowledge_base as kb_search
            result = kb_search.invoke({"query": query.strip(), "domain": domain})
            
            await self.send_data_message("tool_result", f"Searched knowledge base for '{query}'", {
                "tool": "search_knowledge_base",
                "query": query,
                "domain": domain
            })
            
            return result
            
        except Exception as e:
            error_msg = f"Error searching knowledge base: {str(e)}"
            logger.error(f"❌ Tool error: {error_msg}")
            await self.send_data_message("tool_error", error_msg, {"tool": "search_knowledge_base"})
            return error_msg

    @function_tool
    async def get_system_status(self, context: RunContext):
        """Get current system status and health metrics.
        
        Returns information about system performance and any active alerts.
        """
        logger.info("🔧 Tool: get_system_status()")
        
        try:
            # Get basic system info
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status = {
                "status": "operational",
                "cpu_usage": f"{cpu_percent:.1f}%",
                "memory_usage": f"{memory.percent:.1f}%",
                "disk_usage": f"{disk.percent:.1f}%",
                "timestamp": time.time()
            }
            
            # Determine overall health
            if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
                status["status"] = "warning"
            
            await self.send_data_message("tool_result", "Retrieved system status", {
                "tool": "get_system_status",
                "status": status["status"]
            })
            
            return f"System Status: {status['status'].upper()}\nCPU: {status['cpu_usage']}, Memory: {status['memory_usage']}, Disk: {status['disk_usage']}"
            
        except Exception as e:
            error_msg = f"Error retrieving system status: {str(e)}"
            logger.error(f"❌ Tool error: {error_msg}")
            await self.send_data_message("tool_error", error_msg, {"tool": "get_system_status"})
            return error_msg

# ...



    # ==============================================================================
    # Tool Definitions (mirrors BestBox tools)
    # ==============================================================================

    @function_tool
    async def get_top_vendors(self, context: RunContext, limit: int = 5):
        """Get the top vendors by spend.
        
        Args:
            limit: Number of top vendors to return (default: 5)
        """
        logger.info(f"Tool called: get_top_vendors(limit={limit})")
        
        # Import and call actual BestBox tool
        try:
            from tools.erp_tools import get_top_vendors as erp_get_top_vendors
            result = erp_get_top_vendors.invoke({"limit": limit})
            return result
        except Exception as e:
            logger.error(f"Error calling get_top_vendors: {e}")
            return f"Error retrieving vendor data: {str(e)}"

    @function_tool
    async def get_inventory_levels(self, context: RunContext, warehouse: str = "all"):
        """Check current inventory levels.
        
        Args:
            warehouse: Warehouse to check, or 'all' for all warehouses
        """
        logger.info(f"Tool called: get_inventory_levels(warehouse={warehouse})")
        
        try:
            from tools.erp_tools import get_inventory_levels as erp_get_inventory
            result = erp_get_inventory.invoke({"warehouse": warehouse})
            return result
        except Exception as e:
            logger.error(f"Error calling get_inventory_levels: {e}")
            return f"Error retrieving inventory: {str(e)}"

    @function_tool
    async def get_customer_info(self, context: RunContext, customer_name: str):
        """Look up customer information from CRM.
        
        Args:
            customer_name: Name of the customer to look up
        """
        logger.info(f"Tool called: get_customer_info(customer={customer_name})")
        
        try:
            from tools.crm_tools import get_customer_360
            result = get_customer_360.invoke({"customer_name": customer_name})
            return result
        except Exception as e:
            logger.error(f"Error calling get_customer_360: {e}")
            return f"Error retrieving customer data: {str(e)}"

    @function_tool
    async def search_knowledge_base(self, context: RunContext, query: str, domain: str = None):
        """Search the company knowledge base for procedures, policies, or documentation.
        
        Args:
            query: Search query
            domain: Optional domain filter (erp, crm, it_ops, oa)
        """
        logger.info(f"Tool called: search_knowledge_base(query={query}, domain={domain})")
        
        try:
            from tools.rag_tools import search_knowledge_base as kb_search
            result = kb_search.invoke({"query": query, "domain": domain})
            return result
        except Exception as e:
            logger.error(f"Error calling search_knowledge_base: {e}")
            return f"Error searching knowledge base: {str(e)}"


# ==============================================================================
# Agent Server Setup
# ==============================================================================

async def request_fnc(ctx: JobRequest):
    logger.info(f"Received job request for room {ctx.job.room.name}")
    await ctx.accept()

server = AgentServer(
    job_memory_warn_mb=4096, # Increase to 4GB for local LLM
)


def prewarm(proc: JobProcess):
    """Preload models for faster session startup."""
    logger.info("Prewarming: Loading VAD model...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("Prewarming complete")

    # Memory monitoring will be started in the session entrypoint
    logger.info("Prewarming complete - memory monitor will start with session")


server.setup_fnc = prewarm


async def monitor_memory():
    """
    Monitor memory usage and trigger garbage collection when needed.
    Runs continuously in the background.
    """
    process = psutil.Process()
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            mem_mb = process.memory_info().rss / 1024 / 1024

            if mem_mb > 3000:  # 3GB threshold
                logger.warning(f"High memory usage detected: {mem_mb:.1f}MB - forcing garbage collection")
                gc.collect()
                # Log memory after GC
                mem_after = process.memory_info().rss / 1024 / 1024
                logger.info(f"Memory after GC: {mem_after:.1f}MB (freed {mem_mb - mem_after:.1f}MB)")
            elif mem_mb > 2000:  # 2GB warning threshold
                logger.info(f"Memory usage: {mem_mb:.1f}MB (warning threshold)")
            else:
                logger.debug(f"Memory usage: {mem_mb:.1f}MB (healthy)")
        except Exception as e:
            logger.error(f"Error in memory monitor: {e}")


async def entrypoint(ctx: JobContext):
    """
    Production-ready BestBox Voice Agent entrypoint.
    
    Builds on the working simple agent foundation with robust error handling.
    """
    logger.info(f"🎯 BESTBOX SESSION START - Room: {ctx.room.name}")
    
    session_start_time = time.time()
    
    try:
        # Phase 1: Initialize core session configuration
        logger.info("🔧 Phase 1: Initializing session configuration...")
        
        # Get VAD from userdata or load it lazy
        vad = ctx.proc.userdata.get("vad")
        if vad is None:
            logger.info("🔄 VAD not found in userdata, loading now...")
            vad = silero.VAD.load()
            ctx.proc.userdata["vad"] = vad
            
        session_config = {
            "vad": vad,
            "preemptive_generation": True,
            "resume_false_interruption": True,
            "false_interruption_timeout": 1.0,
        }
        
        # Phase 2: Configure STT using provider factory
        logger.info("🔧 Phase 2: Configuring Speech-to-Text...")
        with open("/tmp/bestbox_debug.log", "a") as f:
            f.write("DEBUG: Phase 2 entering\n")
        stt_success = False

        try:
            from services.speech_providers import create_stt

            session_config["stt"] = await create_stt()
            logger.info(f"✅ STT initialized successfully")
            stt_success = True
            with open("/tmp/bestbox_debug.log", "a") as f:
                f.write("DEBUG: Phase 2 done\n")
        except Exception as e:
            logger.error(f"❌ STT initialization failed: {e}", exc_info=True)
            logger.warning(f"⚠️ STT unavailable, continuing without STT")
        
        # Phase 3: Configure LLM with robust fallbacks
        logger.info("🔧 Phase 3: Configuring Language Model...")
        llm_success = False

        # Use LangGraph integration for dual response format (VOICE/TEXT)
        if LANGGRAPH_INTEGRATION and bestbox_graph:
            try:
                logger.info("⚡ Using LangGraph with graph_wrapper for dual response format...")
                from livekit.plugins import langchain as lk_langchain

                # Wrap graph_wrapper as a LangChain Runnable
                from langchain_core.runnables import RunnableLambda
                wrapped_graph = RunnableLambda(graph_wrapper)

                # Create LangChain LLM adapter
                llm_instance = lk_langchain.LLM(llm=wrapped_graph)
                session_config["llm"] = llm_instance
                logger.info("✅ LangGraph integration configured (dual response format)")
                llm_success = True
            except Exception as e:
                logger.error(f"❌ LangGraph integration failed: {e}")
                logger.info("Falling back to direct LLM...")

        # Fallback to direct local LLM if LangGraph fails
        if not llm_success:
            try:
                logger.info("Using direct local LLM...")
                from livekit.plugins import openai as lk_openai

                LOCAL_LLM_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
                model_name = LOCAL_LLM_MODEL

                llm_instance = lk_openai.LLM(
                    base_url=LOCAL_LLM_BASE_URL,
                    model=model_name,
                    api_key="not-needed"
                )
                session_config["llm"] = llm_instance
                logger.info(f"✅ Direct Local LLM configured: {LOCAL_LLM_MODEL} at {LOCAL_LLM_BASE_URL}")
                llm_success = True
            except Exception as e:
                logger.error(f"❌ Local LLM failed: {e}")

        # Fallback to Nvidia LLM if local fails
        if not llm_success:
            try:
                logger.info("Falling back to Nvidia LLM...")
                from livekit.plugins import openai as lk_openai

                NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
                NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
                NVIDIA_MODEL = "minimaxai/minimax-m2"

                if not NVIDIA_API_KEY:
                    raise RuntimeError("NVIDIA_API_KEY is not configured")

                llm_instance = lk_openai.LLM(
                    base_url=NVIDIA_BASE_URL,
                    model=NVIDIA_MODEL,
                    api_key=NVIDIA_API_KEY
                )
                session_config["llm"] = llm_instance
                logger.info(f"✅ Nvidia LLM configured: {NVIDIA_MODEL}")
                llm_success = True
            except Exception as e:
                logger.error(f"❌ Nvidia LLM failed: {e}")
        
        # Create minimal LLM if all else fails
        if not llm_success:
            logger.warning("⚠️ Creating minimal fallback LLM")
            # Continue without LLM - session will still work for audio testing
        
        # Phase 4: Configure TTS using provider factory
        logger.info("🔧 Phase 4: Configuring Text-to-Speech...")
        tts_success = False

        try:
            from services.speech_providers import create_tts

            session_config["tts"] = await create_tts()
            logger.info(f"✅ TTS initialized successfully")
            tts_success = True
        except Exception as e:
            logger.error(f"❌ TTS initialization failed: {e}", exc_info=True)
            logger.warning(f"⚠️ TTS unavailable, continuing without TTS")
        
        # Phase 5: Optional turn detection
        # DISABLED for debugging - relying on VAD
        # if TURN_DETECTOR_AVAILABLE and MultilingualModel:
        #     try:
        #         session_config["turn_detection"] = MultilingualModel()
        #         logger.info("✅ Turn detection enabled")
        #     except Exception as e:
        #         logger.warning(f"⚠️ Turn detection failed: {e}")

        # Phase 6: Create and start session
        logger.info("🔧 Phase 5: Creating agent session...")
        # NOTE: session_config now contains: vad, stt, llm, tts
        session = AgentSession(**session_config)
        
        # Set up metrics collection
        usage_collector = metrics.UsageCollector()
        
        @session.on("metrics_collected")
        def _on_metrics_collected(ev: MetricsCollectedEvent):
            try:
                metrics.log_metrics(ev.metrics)
                usage_collector.collect(ev.metrics)
            except Exception as e:
                logger.debug(f"Metrics error: {e}")
        
        # ASR BRIDGE HOOKS: Send transcripts to frontend via data channel
        # These hooks send user transcripts and agent responses to CopilotKit message box
        # NOTE: Callbacks must be synchronous, use asyncio.create_task for async operations

        async def send_transcript_data(transcript: str):
            """Helper to send transcript via data channel."""
            payload = json.dumps({
                "type": "user_transcript",
                "text": transcript,
                "timestamp": time.time()
            }).encode('utf-8')
            await ctx.room.local_participant.publish_data(payload, reliable=True)
            logger.info(f"📡 Sent user transcript via data channel: '{transcript[:50]}...'")

        async def send_agent_response_data(response: str):
            """Helper to send agent response via data channel."""
            # Send agent response
            payload = json.dumps({
                "type": "agent_response",
                "text": response,
                "timestamp": time.time()
            }).encode('utf-8')
            await ctx.room.local_participant.publish_data(payload, reliable=True)

            # Send completion marker
            await asyncio.sleep(0.1)  # Brief delay
            complete_payload = json.dumps({
                "type": "agent_response_complete",
                "timestamp": time.time()
            }).encode('utf-8')
            await ctx.room.local_participant.publish_data(complete_payload, reliable=True)
            logger.info(f"📡 Sent agent response via data channel: '{response[:50]}...'")

        @session.on("user_input_transcribed")
        def on_user_input_transcribed(ev):
            """Called when user speech is transcribed."""
            transcript = ev.transcript if hasattr(ev, 'transcript') else str(ev)
            logger.info(f"🎤 User input transcribed: '{transcript}'")
            # Create async task to send data
            asyncio.create_task(send_transcript_data(transcript))

        @session.on("conversation_item_added")
        def on_conversation_item_added(ev):
            """Called when any conversation item is added (user or agent)."""
            item = ev.item if hasattr(ev, 'item') else ev

            # Check if it's an agent message
            if hasattr(item, 'role') and item.role == 'assistant':
                # Extract content - handle different formats
                content = None
                if hasattr(item, 'content'):
                    raw_content = item.content

                    # Handle list of content chunks
                    if isinstance(raw_content, list):
                        # Extract text from list items
                        content_parts = []
                        for chunk in raw_content:
                            if hasattr(chunk, 'text'):
                                content_parts.append(chunk.text)
                            elif isinstance(chunk, str):
                                content_parts.append(chunk)
                            else:
                                content_parts.append(str(chunk))
                        content = ''.join(content_parts)
                    elif hasattr(raw_content, 'text'):
                        # Single chunk with text attribute
                        content = raw_content.text
                    else:
                        # Direct string or other
                        content = str(raw_content)
                else:
                    content = str(item)

                logger.info(f"🤖 Agent message added - raw type: {type(item.content if hasattr(item, 'content') else item)}")
                logger.info(f"🤖 Agent message content: '{content[:100] if content else '(empty)'}...'")

                if content and str(content).strip():
                    # Parse dual response format
                    parsed = parse_dual_response(str(content))

                    logger.info(f"📝 Parsed response - Voice: '{parsed['voice'][:50]}...' | Text: '{parsed['text'][:50]}...'")

                    # Send TEXT portion to chat (detailed version)
                    # VOICE portion is automatically spoken by TTS via agent session
                    asyncio.create_task(send_agent_response_data(parsed['text']))

        # Add cleanup callback
        async def log_usage():
            try:
                summary = usage_collector.get_summary()
                logger.info(f"Session usage: {summary}")
            except Exception as e:
                logger.debug(f"Usage logging error: {e}")
        
        ctx.add_shutdown_callback(log_usage)
        
        # Start memory monitoring
        asyncio.create_task(monitor_memory())
        
        # Phase 7: Start session with voice agent + TTS
        logger.info("🔧 Phase 6: Starting session with voice-enabled agent...")

        # Get LLM from session_config to pass to agent
        # CRITICAL: LLM and TTS must be passed to Agent for the loop to work
        agent_llm = session_config.get("llm")
        agent_tts = session_config.get("tts")

        # Create BestBoxVoiceAgent with LLM and TTS
        agent = BestBoxVoiceAgent(llm=agent_llm, tts=agent_tts)
        logger.info(f"✅ BestBox Voice Agent created with LLM={agent_llm is not None}, TTS={agent_tts is not None}")

        # Configure room input options to prevent premature disconnect
        from livekit.agents import RoomInputOptions
        room_input_opts = RoomInputOptions(
            close_on_disconnect=False  # Keep session alive even if participant briefly disconnects
        )

        # Start session with agent and TTS (TTS is configured in session, not agent)
        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=room_input_opts
        )
        
        session_init_time = time.time() - session_start_time
        logger.info(f"✅ SESSION READY in {session_init_time:.2f}s - Room: {ctx.room.name}")
        
        # Phase 9: Generate greeting audio (musical beep)
        await asyncio.sleep(0.5)  # Let session stabilize
        
        logger.info("🔊 Phase 8: Generating greeting audio...")
        try:
            await generate_greeting_audio(ctx.room)
            logger.info("✅ Greeting audio completed")

            # Send text greeting to CopilotKit chat
            # Use "greeting" type to avoid adding to conversation history
            greeting_text = "你好!我是BestBox智能助手,很高兴为您服务。"
            payload = json.dumps({
                "type": "greeting",
                "text": greeting_text,
                "timestamp": time.time()
            }).encode('utf-8')
            await ctx.room.local_participant.publish_data(payload, reliable=True)
            logger.info(f"✅ Greeting text sent: {greeting_text}")
        except Exception as e:
            logger.error(f"❌ Greeting audio failed: {e}")

        logger.info("🎯 BESTBOX SESSION READY - All systems operational")
        
    except Exception as e:
        session_time = time.time() - session_start_time
        logger.error(f"❌ SESSION FAILED after {session_time:.2f}s: {e}", exc_info=True)
        
        # Try to create a minimal fallback session
        try:
            logger.info("🔄 Attempting minimal fallback session...")
            # Use the already loaded vad if available
            fallback_vad = ctx.proc.userdata.get("vad") or silero.VAD.load()
            minimal_session = AgentSession(vad=fallback_vad)
            minimal_agent = BestBoxVoiceAgent()
            await minimal_session.start(agent=minimal_agent, room=ctx.room)
            logger.info("✅ Minimal fallback session started")

            # Still try greeting
            await generate_greeting_audio(ctx.room)

            # Send text greeting
            # Use "greeting" type to avoid adding to conversation history
            greeting_text = "你好!我是BestBox智能助手,很高兴为您服务。"
            payload = json.dumps({
                "type": "greeting",
                "text": greeting_text,
                "timestamp": time.time()
            }).encode('utf-8')
            await ctx.room.local_participant.publish_data(payload, reliable=True)
            
        except Exception as fallback_error:
            logger.error(f"❌ Fallback session also failed: {fallback_error}")
            raise


async def generate_greeting_audio(room):
    """Generate and play greeting audio tone."""
    try:
        from livekit import rtc
        import numpy as np
        
        # Create audio source and track
        source = rtc.AudioSource(48000, 1)
        track = rtc.LocalAudioTrack.create_audio_track("bestbox_greeting", source)
        
        # Publish track
        pub = await room.local_participant.publish_track(track)
        logger.info("📡 Greeting track published")
        
        # Generate pleasant greeting tone sequence
        sample_rate = 48000
        
        # Create a pleasant chord progression: C-E-G (major triad)
        frequencies = [261.63, 329.63, 392.00]  # C4, E4, G4
        duration_per_note = 0.6
        total_duration = len(frequencies) * duration_per_note
        
        all_samples = []
        
        for i, freq in enumerate(frequencies):
            note_samples = int(duration_per_note * sample_rate)
            t = np.arange(note_samples) / sample_rate
            
            # Generate note with envelope
            amplitude = 32767 * 0.25  # 25% volume
            wave = amplitude * np.sin(2 * np.pi * freq * t)
            
            # Add envelope (attack, sustain, release)
            attack_samples = int(0.1 * sample_rate)
            release_samples = int(0.2 * sample_rate)
            
            # Attack
            for j in range(min(attack_samples, len(wave))):
                wave[j] *= (j / attack_samples)
            
            # Release
            for j in range(min(release_samples, len(wave))):
                wave[-(j+1)] *= (j / release_samples)
            
            all_samples.extend(wave.astype(np.int16))
        
        # Convert to bytes
        audio_bytes = np.array(all_samples, dtype=np.int16).tobytes()
        
        # Send in 10ms chunks
        chunk_size = 480 * 2  # 10ms at 48kHz, 16-bit
        samples_per_chunk = 480
        
        logger.info(f"🎵 Playing greeting chord sequence ({len(all_samples)} samples)")
        
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            
            # Pad if needed
            if len(chunk) < chunk_size:
                chunk = chunk + b"\0" * (chunk_size - len(chunk))
            
            frame = rtc.AudioFrame(
                data=chunk,
                sample_rate=48000,
                num_channels=1,
                samples_per_channel=samples_per_chunk
            )
            
            await source.capture_frame(frame)
            await asyncio.sleep(0.01)  # 10ms delay
        
        logger.info("🎵 Greeting playback completed")
        
        # Wait before unpublishing
        await asyncio.sleep(0.3)
        await room.local_participant.unpublish_track(pub.sid)
        logger.info("📡 Greeting track unpublished")
        
    except Exception as e:
        logger.error(f"❌ Greeting audio generation failed: {e}", exc_info=True)
    
    # Trigger initial greeting manually via LLM chat if supported?
    # agent.session.chat_ctx.append(...)
    # For now, let's rely on user speaking first or find a way later.
    # The previous on_enter used session.generate_reply() which might not exist on Session.



# ==============================================================================
# Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    if not LIVEKIT_AVAILABLE:
        print("LiveKit agents not available. Install with:")
        print("  pip install 'livekit-agents[silero,langchain,turn-detector]~=1.0'")
        sys.exit(1)
    
    print("=" * 60)
    print("BestBox Voice Agent (LiveKit)")
    print("=" * 60)
    print(f"Local LLM: {LOCAL_LLM_URL}")
    print(f"STT Model: {STT_MODEL}")
    print(f"TTS Model: {TTS_MODEL}")
    print(f"LangGraph Integration: {LANGGRAPH_INTEGRATION}")
    print("=" * 60)
    
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            request_fnc=request_fnc,
            agent_name="BestBoxVoiceAgent",
        )
    )
