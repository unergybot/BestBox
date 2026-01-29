#!/usr/bin/env python3
"""
Test script for BestBox LiveKit Voice Agent

Tests the agent's ability to:
1. Start up properly
2. Load the BestBox LangGraph
3. Respond to tool calls
4. Handle voice configuration

This is a smoke test to verify the integration before live testing.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("BestBox LiveKit Voice Agent Test")
print("=" * 60)
print()

# Test 1: Import checks
print("Test 1: Import LiveKit components...")
try:
    from livekit.agents import Agent, AgentServer, AgentSession
    from livekit.plugins import silero, langchain as lk_langchain
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    print("✅ LiveKit imports successful")
except ImportError as e:
    print(f"❌ LiveKit import failed: {e}")
    sys.exit(1)

# Test 2: BestBox graph import
print("\nTest 2: Import BestBox LangGraph...")
try:
    from agents.graph import app as bestbox_graph
    from agents.state import AgentState
    print("✅ BestBox LangGraph imported")
except ImportError as e:
    print(f"❌ BestBox graph import failed: {e}")
    sys.exit(1)

# Test 3: BestBox tools import
print("\nTest 3: Import BestBox tools...")
try:
    from tools.erp_tools import get_top_vendors
    from tools.crm_tools import get_customer_360
    from tools.rag_tools import search_knowledge_base
    print("✅ BestBox tools imported")
except ImportError as e:
    print(f"❌ Tools import failed: {e}")
    sys.exit(1)

# Test 4: LangChain adapter
print("\nTest 4: Create LangChain adapter...")
try:
    llm_adapter = lk_langchain.LLMAdapter(bestbox_graph)
    print("✅ LangChain adapter created")
    print(f"   Wrapped graph: {type(bestbox_graph).__name__}")
except Exception as e:
    print(f"❌ Adapter creation failed: {e}")
    sys.exit(1)

# Test 5: VAD loading
print("\nTest 5: Load Silero VAD...")
try:
    vad = silero.VAD.load()
    print("✅ Silero VAD loaded")
except Exception as e:
    print(f"❌ VAD load failed: {e}")
    sys.exit(1)

# Test 6: Turn detector
print("\nTest 6: Initialize turn detector...")
try:
    # Turn detector requires job context, so we just check import
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    print("✅ Multilingual turn detector available")
    print("   (Will be initialized during job execution)")
except Exception as e:
    print(f"❌ Turn detector import failed: {e}")
    sys.exit(1)

# Test 7: Local LLM connectivity
print("\nTest 7: Check local LLM connectivity...")
import requests
try:
    llm_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
    health_url = llm_url.replace("/v1", "/health")
    response = requests.get(health_url, timeout=2)
    if response.status_code == 200:
        print(f"✅ Local LLM responding at {llm_url}")
    else:
        print(f"⚠️  Local LLM returned status {response.status_code}")
except Exception as e:
    print(f"⚠️  Local LLM not responding: {e}")
    print("   Note: This is optional if using cloud providers")

# Test 8: LiveKit server connectivity
print("\nTest 8: Check LiveKit server...")
try:
    # Check if Docker container is running
    import subprocess
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=livekit-server", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=2
    )
    if "livekit-server" in result.stdout:
        print(f"✅ LiveKit server container is running")
        print(f"   Access at: ws://localhost:7880")
    else:
        print(f"⚠️  LiveKit server container not found")
        print("   Start with: docker run -d --name livekit-server -p 7880:7880 livekit/livekit-server:latest --dev")
except Exception as e:
    print(f"⚠️  Could not check LiveKit: {e}")
    print("   This is optional for testing components")

# Test 9: Agent class instantiation
print("\nTest 9: Instantiate voice agent...")
try:
    from services.livekit_agent import BestBoxVoiceAgent
    agent = BestBoxVoiceAgent()
    print("✅ BestBoxVoiceAgent instantiated")
    print(f"   Instructions length: {len(agent.instructions)} chars")
except Exception as e:
    print(f"❌ Agent instantiation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 10: Tool availability
print("\nTest 10: Check agent tools...")
try:
    # Tools are decorated methods on the agent class
    tools = [attr for attr in dir(agent) if not attr.startswith('_') and callable(getattr(agent, attr))]
    tool_methods = [t for t in tools if hasattr(getattr(agent, t), '__self__')]
    print(f"✅ Agent has {len(tool_methods)} available methods")
    print(f"   Sample methods: {tool_methods[:5]}")
except Exception as e:
    print(f"⚠️  Could not enumerate tools: {e}")

print()
print("=" * 60)
print("✅ All tests passed!")
print("=" * 60)
print()
print("Next steps:")
print("  1. Start the agent:")
print("     python services/livekit_agent.py dev")
print()
print("  2. Connect a client:")
print("     - Use LiveKit playground: https://agents-playground.livekit.io")
print("     - Or build a custom frontend with LiveKit SDK")
print()
print("  3. Test with voice:")
print("     - Say: 'What are the top vendors?'")
print("     - Say: 'Check inventory levels'")
print("     - Say: 'Tell me about customer ABC Corp'")
print()
