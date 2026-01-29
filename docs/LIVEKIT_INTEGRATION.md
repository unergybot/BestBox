# LiveKit Integration Analysis for BestBox

**Date:** January 25, 2026  
**Status:** 📋 Analysis Complete  
**Purpose:** Evaluate LiveKit Agents vs Current S2S Implementation

---

## 🔍 Executive Summary

**Recommendation:** LiveKit Agents offers **significant advantages** over the current custom S2S implementation, especially for:
- Real-time streaming with lower latency
- Production-grade WebRTC infrastructure
- Built-in semantic turn detection
- Native LangGraph integration
- Reduced development/maintenance burden

---

## 📊 Comparison: Current BestBox S2S vs LiveKit Agents

| Feature | Current BestBox S2S | LiveKit Agents |
|---------|---------------------|----------------|
| **Architecture** | Custom WebSocket server | WebRTC-based SFU |
| **ASR** | faster-whisper (local) | Deepgram, Whisper cloud, or local |
| **VAD** | webrtcvad | Silero VAD (ONNX, better accuracy) |
| **TTS** | XTTS v2 / Piper | Cartesia, ElevenLabs, OpenAI, or custom |
| **LLM** | Local Qwen via LangGraph | OpenAI, Anthropic, or custom via LangGraph adapter |
| **Turn Detection** | Simple silence-based | ML-based semantic turn detector |
| **Streaming** | Manual chunk buffering | Native token-level streaming |
| **Latency** | ~2-5s end-to-end | ~200-800ms with optimized stack |
| **Interruption Handling** | Basic | Advanced (resumable, false positive detection) |
| **Multi-user** | Limited | Native support |
| **Echo Cancellation** | None | Krisp BVC integration |
| **Observability** | Custom | Built-in metrics collector |
| **Development Effort** | High (custom everything) | Low (use plugins) |
| **Local Deployment** | ✅ Full local | ✅ Self-hostable |

---

## 🚀 LiveKit Agents Advantages

### 1. **Semantic Turn Detection**
Current BestBox uses simple silence detection (VAD). LiveKit has a trained transformer model that understands *when the user is done speaking*, reducing false interruptions.

```python
from livekit.plugins.turn_detector.multilingual import MultilingualModel

session = AgentSession(
    turn_detection=MultilingualModel(),  # ML-based turn detection
    resume_false_interruption=True,      # Automatically resume if false positive
)
```

### 2. **Native LangGraph Integration**
LiveKit provides a `langchain.LLMAdapter` that wraps your existing LangGraph graphs:

```python
from livekit.plugins import langchain

# Your existing BestBox graph
from agents.graph import app as agent_app

agent = Agent(
    llm=langchain.LLMAdapter(agent_app),  # Wrap existing graph!
)
```

### 3. **Preemptive Response Generation**
Start generating responses *before* the user finishes speaking:

```python
session = AgentSession(
    preemptive_generation=True,  # Start LLM while user still talking
)
```

### 4. **Token-Level TTS Streaming**
TTS starts speaking as tokens arrive, not after full response:

```python
# Built into the framework - no manual chunking needed
tts=inference.TTS("cartesia/sonic-3")  # Streams automatically
```

### 5. **Production WebRTC Infrastructure**
- UDP/TCP fallback
- TURN server support
- Network resilience
- Mobile SDK support

---

## 🔧 How to Use LiveKit with BestBox

### Step 1: Install Dependencies

```bash
pip install "livekit-agents[silero,langchain,turn-detector]~=1.0"
pip install livekit-plugins-openai  # For OpenAI-compatible API
```

### Step 2: Install LiveKit Server

```bash
# Option A: Binary
cd ~/MyCode/livekit
./install-livekit.sh

# Option B: Docker
docker run -d --name livekit \
  -p 7880:7880 -p 7881:7881/tcp -p 50000-60000:50000-60000/udp \
  livekit/livekit-server:latest \
  --dev  # Development mode with auto-generated keys
```

### Step 3: Create BestBox LiveKit Agent

```python
# services/livekit_agent.py
import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent, AgentServer, AgentSession, JobContext, JobProcess, cli, inference
)
from livekit.plugins import langchain, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import existing BestBox graph
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.graph import app as bestbox_graph

load_dotenv()
logger = logging.getLogger("bestbox-voice")

server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload models for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


class BestBoxVoiceAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are BestBox AI Assistant. Keep responses concise for voice. "
                "You can help with ERP, CRM, IT Ops, and Office Automation."
            ),
        )

    async def on_enter(self):
        # Greet user when they join
        self.session.generate_reply(
            instructions="Greet the user briefly and ask how you can help.",
            allow_interruptions=False
        )


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entry point for voice sessions."""
    
    session = AgentSession(
        # Use Silero VAD for voice activity detection
        vad=ctx.proc.userdata["vad"],
        
        # STT: Use Deepgram or configure local Whisper
        # For local: implement custom STT plugin
        stt=inference.STT("deepgram/nova-3", language="multi"),
        
        # LLM: Wrap BestBox LangGraph
        llm=langchain.LLMAdapter(bestbox_graph),
        
        # TTS: Use Cartesia or configure local Piper
        # For local: implement custom TTS plugin  
        tts=inference.TTS("cartesia/sonic-3"),
        
        # ML-based turn detection
        turn_detection=MultilingualModel(),
        
        # Advanced features
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    await session.start(
        agent=BestBoxVoiceAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
```

### Step 4: Configure for Local LLM

Set environment variable to point to your local llama-server:

```bash
export OPENAI_BASE_URL="http://localhost:8080/v1"
export OPENAI_API_KEY="sk-no-key-required"
```

Or in the code:

```python
from livekit.plugins import openai as lk_openai

# Configure custom LLM endpoint
llm = lk_openai.LLM(
    base_url="http://localhost:8080/v1",
    model="qwen2.5-14b",
)
```

### Step 5: Run the Agent

```bash
# Start LiveKit server
livekit-server --dev

# In another terminal, start the agent
cd /home/unergy/BestBox
python services/livekit_agent.py dev
```

---

## 🔌 Local-Only Configuration

For fully local deployment without cloud services:

### Local STT (Custom Plugin)

You'll need to create a custom STT plugin wrapping faster-whisper:

```python
# services/livekit_plugins/local_stt.py
from livekit.agents import stt
from faster_whisper import WhisperModel

class LocalWhisperSTT(stt.STT):
    def __init__(self, model_size="large-v3"):
        super().__init__()
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    async def transcribe(self, audio_data: bytes) -> str:
        # Implement transcription
        segments, _ = self.model.transcribe(audio_data)
        return " ".join(s.text for s in segments)
```

### Local TTS (Piper Plugin)

```python
# services/livekit_plugins/local_tts.py
from livekit.agents import tts
import subprocess

class LocalPiperTTS(tts.TTS):
    def __init__(self, model_path: str):
        super().__init__()
        self.model_path = model_path
    
    async def synthesize(self, text: str) -> bytes:
        # Use Piper CLI
        result = subprocess.run(
            ["piper", "--model", self.model_path, "--output-raw"],
            input=text.encode(),
            capture_output=True
        )
        return result.stdout
```

---

## 📁 Files in Your LiveKit Repos

### ~/MyCode/livekit/ (Server)
- Go-based WebRTC SFU server
- Self-hostable, single binary
- Handles all WebRTC complexity

### ~/MyCode/agents/ (Agent Framework)
- Python framework for voice AI
- `livekit-agents/` - Core agent framework
- `livekit-plugins/` - 50+ plugins for STT/TTS/LLM
- `examples/voice_agents/langgraph_agent.py` - **Ready-to-use LangGraph example!**

---

## 🎯 Migration Plan

### Phase 1: Proof of Concept (1-2 days)
1. Install LiveKit server locally
2. Adapt `langgraph_agent.py` example with BestBox graph
3. Test with cloud STT/TTS (Deepgram + Cartesia)

### Phase 2: Local STT/TTS (3-5 days)
1. Create custom faster-whisper STT plugin
2. Create custom Piper TTS plugin
3. Test end-to-end locally

### Phase 3: Production (1 week)
1. Configure LiveKit server with proper keys
2. Deploy behind load balancer
3. Integrate with CopilotKit frontend
4. Add observability/metrics

---

## 💡 Key Takeaways

1. **LiveKit solves the hard problems** - WebRTC, turn detection, interruption handling
2. **Your LangGraph stays intact** - Just wrap with `LLMAdapter`
3. **Cloud providers give fastest latency** - But local is possible with custom plugins
4. **The `langgraph_agent.py` example** is your starting point

---

## 🔗 Resources

- LiveKit Agents Docs: https://docs.livekit.io/agents/
- LangGraph Integration: `~/MyCode/agents/examples/voice_agents/langgraph_agent.py`
- Local Plugin Examples: `~/MyCode/agents/livekit-plugins/`
- LiveKit Server Config: `~/MyCode/livekit/config-sample.yaml`
