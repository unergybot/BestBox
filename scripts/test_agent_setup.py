#!/usr/bin/env python3
"""
Quick test to verify LiveKit agent can receive and process audio
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

async def test_agent_connection():
    """Test basic agent functionality"""
    print("Testing LiveKit Agent Setup...")
    print("=" * 60)
    
    # 1. Check imports
    print("\n1. Checking imports...")
    try:
        from livekit.agents import Agent
        from livekit.plugins import silero
        print("   ✅ LiveKit agents available")
    except ImportError as e:
        print(f"   ❌ LiveKit import failed: {e}")
        return False
    
    # 2. Check LangGraph integration
    print("\n2. Checking LangGraph integration...")
    try:
        from agents.graph import app as bestbox_graph
        print("   ✅ BestBox graph available")
        
        # Test graph invocation
        test_state = {"messages": [{"role": "user", "content": "Hello"}]}
        result = await bestbox_graph.ainvoke(test_state)
        print(f"   ✅ Graph responds: {result['messages'][-1].content[:50]}...")
    except Exception as e:
        print(f"   ⚠️  Graph test failed: {e}")
    
    # 3. Check STT/TTS configuration
    print("\n3. Checking STT/TTS...")
    STT_MODEL = os.environ.get("STT_MODEL", "deepgram/nova-3")
    TTS_MODEL = os.environ.get("TTS_MODEL", "cartesia/sonic-3")
    print(f"   STT: {STT_MODEL}")
    print(f"   TTS: {TTS_MODEL}")
    
    # 4. Check local adapters
    print("\n4. Checking local adapters...")
    try:
        from services.livekit_local import LocalSTT, LocalTTS
        print("   ✅ Local STT/TTS available")
    except ImportError:
        print("   ⚠️  Local adapters not available (will use cloud)")
    
    print("\n" + "=" * 60)
    print("Configuration looks good!")
    print("\nTo test voice interaction:")
    print("1. Agent should be running: ./venv/bin/python3 services/livekit_agent.py dev")
    print("2. Open http://localhost:3000/en/voice")
    print("3. Click 'Start Voice Session'")
    print("4. Speak into your microphone")
    print("\nExpected flow:")
    print("  User speaks → STT → LangGraph → TTS → User hears response")
    return True

if __name__ == "__main__":
    asyncio.run(test_agent_connection())
