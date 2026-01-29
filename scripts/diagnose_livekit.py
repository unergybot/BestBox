#!/usr/bin/env python3
"""
LiveKit End-to-End Diagnostic Script

Tests every component of the voice pipeline and measures latency.
NO SILENT FAILURES - Everything is loud and explicit.

Usage:
    python scripts/diagnose_livekit.py
"""

import sys
import os
import time
import json
import asyncio
import requests
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Colors for terminal output
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{text.center(80)}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}\n")

def print_test(name: str):
    print(f"{Color.BOLD}{Color.BLUE}[TEST]{Color.END} {name}...", end=" ", flush=True)

def print_pass(message: str = "PASS", latency_ms: Optional[float] = None):
    if latency_ms is not None:
        print(f"{Color.GREEN}✓ {message} ({latency_ms:.1f}ms){Color.END}")
    else:
        print(f"{Color.GREEN}✓ {message}{Color.END}")

def print_fail(message: str):
    print(f"{Color.RED}✗ FAIL: {message}{Color.END}")

def print_warning(message: str):
    print(f"{Color.YELLOW}⚠ WARNING: {message}{Color.END}")

def print_info(message: str):
    print(f"{Color.CYAN}ℹ {message}{Color.END}")

def print_metric(name: str, value: str):
    print(f"  {Color.MAGENTA}→{Color.END} {name}: {Color.BOLD}{value}{Color.END}")


class DiagnosticResults:
    """Store diagnostic results for final report."""
    def __init__(self):
        self.tests = []
        self.metrics = {}
        self.errors = []

    def add_test(self, name: str, passed: bool, latency_ms: Optional[float] = None, error: str = None):
        self.tests.append({
            "name": name,
            "passed": passed,
            "latency_ms": latency_ms,
            "error": error
        })
        if not passed and error:
            self.errors.append(f"{name}: {error}")

    def add_metric(self, name: str, value: Any):
        self.metrics[name] = value

    def print_summary(self):
        print_header("DIAGNOSTIC SUMMARY")

        passed = sum(1 for t in self.tests if t["passed"])
        total = len(self.tests)

        print(f"Tests: {Color.BOLD}{passed}/{total} passed{Color.END}")

        if self.errors:
            print(f"\n{Color.RED}{Color.BOLD}FAILURES:{Color.END}")
            for error in self.errors:
                print(f"  {Color.RED}✗{Color.END} {error}")

        if self.metrics:
            print(f"\n{Color.MAGENTA}{Color.BOLD}METRICS:{Color.END}")
            for name, value in self.metrics.items():
                print(f"  {name}: {Color.BOLD}{value}{Color.END}")

        print()
        if passed == total:
            print(f"{Color.GREEN}{Color.BOLD}ALL TESTS PASSED ✓{Color.END}")
            return True
        else:
            print(f"{Color.RED}{Color.BOLD}TESTS FAILED - FIX ERRORS ABOVE{Color.END}")
            return False


async def check_livekit_server(results: DiagnosticResults) -> bool:
    """Check if LiveKit server is running."""
    print_header("STAGE 1: INFRASTRUCTURE")

    print_test("LiveKit server (ws://localhost:7880)")

    try:
        # Try to connect to LiveKit HTTP endpoint
        start = time.time()
        response = requests.get("http://localhost:7880", timeout=5)
        latency = (time.time() - start) * 1000

        # Any response means server is up (even 404 is fine)
        print_pass("Server responding", latency)
        results.add_test("LiveKit Server", True, latency)
        return True
    except requests.exceptions.ConnectionError:
        print_fail("Cannot connect - is LiveKit running?")
        print_info("Start with: ./scripts/start-livekit.sh")
        results.add_test("LiveKit Server", False, error="Connection refused")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("LiveKit Server", False, error=str(e))
        return False


async def check_llm_server(results: DiagnosticResults) -> bool:
    """Check if LLM server is running and measure response time."""
    print_test("LLM server (http://localhost:8080)")

    try:
        start = time.time()
        response = requests.get("http://localhost:8080/health", timeout=5)
        latency = (time.time() - start) * 1000

        if response.status_code == 200:
            print_pass("Server healthy", latency)
            results.add_test("LLM Server", True, latency)
            return True
        else:
            print_fail(f"Server returned {response.status_code}")
            results.add_test("LLM Server", False, error=f"HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_fail("Cannot connect - is LLM running?")
        print_info("Start with: ./scripts/start-llm.sh")
        results.add_test("LLM Server", False, error="Connection refused")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("LLM Server", False, error=str(e))
        return False


async def test_llm_inference(results: DiagnosticResults) -> bool:
    """Test LLM inference and measure latency."""
    print_test("LLM inference speed")

    try:
        payload = {
            "model": "qwen",
            "messages": [{"role": "user", "content": "Hello, respond with just 'Hi'"}],
            "temperature": 0.7,
            "max_tokens": 10,
            "stream": False
        }

        start = time.time()
        response = requests.post(
            "http://localhost:8080/v1/chat/completions",
            json=payload,
            timeout=10
        )
        latency = (time.time() - start) * 1000

        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print_pass(f"Response: '{content.strip()}'", latency)
            results.add_test("LLM Inference", True, latency)
            results.add_metric("LLM Response Time", f"{latency:.0f}ms")
            return True
        else:
            print_fail(f"HTTP {response.status_code}: {response.text[:100]}")
            results.add_test("LLM Inference", False, error=f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("LLM Inference", False, error=str(e))
        return False


async def check_agent_process(results: DiagnosticResults) -> bool:
    """Check if LiveKit agent is running."""
    print_test("LiveKit agent process")

    try:
        import subprocess
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if "livekit_agent.py" in result.stdout:
            print_pass("Agent running")
            results.add_test("Agent Process", True)
            return True
        else:
            print_fail("Agent not running")
            print_info("Start with: python services/livekit_agent.py dev")
            results.add_test("Agent Process", False, error="Process not found")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("Agent Process", False, error=str(e))
        return False


async def test_stt_model(results: DiagnosticResults) -> bool:
    """Test STT model loading and inference speed."""
    print_header("STAGE 2: SPEECH-TO-TEXT")

    print_test("Loading STT model (faster-whisper)")

    try:
        from services.speech.asr import StreamingASR, ASRConfig

        # Use same config as agent
        config = ASRConfig(
            model_size="distil-small.en",
            device="cpu",
            compute_type="int8",
            language=""
        )

        start = time.time()
        asr = StreamingASR(config)
        _ = asr.model  # Trigger lazy load
        load_time = (time.time() - start) * 1000

        print_pass(f"Model loaded", load_time)
        results.add_test("STT Model Load", True, load_time)
        results.add_metric("STT Model", config.model_size)

        # Test transcription with dummy audio
        print_test("STT transcription speed")

        import numpy as np
        # Generate 3 seconds of silence (16kHz, mono)
        dummy_audio = np.zeros(16000 * 3, dtype=np.int16)

        start = time.time()
        asr.feed_audio(dummy_audio)
        result = asr.finalize()
        transcribe_time = (time.time() - start) * 1000

        print_pass(f"Transcription complete", transcribe_time)
        results.add_test("STT Transcription", True, transcribe_time)
        results.add_metric("STT Processing Time", f"{transcribe_time:.0f}ms for 3s audio")

        return True

    except ImportError as e:
        print_fail(f"Import error: {e}")
        print_info("Install with: pip install faster-whisper")
        results.add_test("STT Model", False, error=str(e))
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("STT Model", False, error=str(e))
        return False


async def test_tts_model(results: DiagnosticResults) -> bool:
    """Test TTS model loading and synthesis speed."""
    print_header("STAGE 3: TEXT-TO-SPEECH")

    print_test("Loading TTS model")

    try:
        from services.speech.tts import StreamingTTS, TTSConfig

        config = TTSConfig(
            sample_rate=24000,
            fallback_to_piper=True
        )

        start = time.time()
        tts = StreamingTTS(config)
        _ = tts.tts  # Trigger lazy load
        load_time = (time.time() - start) * 1000

        print_pass(f"Model loaded", load_time)
        results.add_test("TTS Model Load", True, load_time)

        # Test synthesis
        print_test("TTS synthesis speed")

        test_text = "Hello, this is a test."
        start = time.time()
        audio = tts.synthesize(test_text, language="en")
        synthesis_time = (time.time() - start) * 1000

        if audio and len(audio) > 0:
            audio_duration_ms = (len(audio) / 2 / 24000) * 1000  # PCM16, 24kHz
            print_pass(f"Synthesized {audio_duration_ms:.0f}ms audio", synthesis_time)
            results.add_test("TTS Synthesis", True, synthesis_time)
            results.add_metric("TTS Speed", f"{synthesis_time:.0f}ms synthesis for {audio_duration_ms:.0f}ms audio")
            return True
        else:
            print_fail("No audio generated")
            results.add_test("TTS Synthesis", False, error="No audio output")
            return False

    except ImportError as e:
        print_fail(f"Import error: {e}")
        results.add_test("TTS Model", False, error=str(e))
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("TTS Model", False, error=str(e))
        return False


async def test_langgraph_integration(results: DiagnosticResults) -> bool:
    """Test LangGraph agent integration."""
    print_header("STAGE 4: LANGGRAPH AGENTS")

    print_test("Loading LangGraph agent")

    try:
        from agents.graph import app as agent_app
        from agents.state import AgentState
        from langchain_core.messages import HumanMessage

        print_pass("Agent loaded")
        results.add_test("LangGraph Load", True)

        # Test agent invocation
        print_test("Agent invocation (router)")

        inputs = {
            "messages": [HumanMessage(content="Hello")],
            "current_agent": "router",
            "tool_calls": 0,
            "confidence": 1.0,
            "context": {},
            "plan": [],
            "step": 0
        }

        start = time.time()
        try:
            result = await asyncio.wait_for(
                agent_app.ainvoke(inputs),
                timeout=10.0
            )
            invoke_time = (time.time() - start) * 1000

            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
                print_pass(f"Response: '{last_msg[:50]}...'", invoke_time)
                results.add_test("Agent Invocation", True, invoke_time)
                results.add_metric("Agent Response Time", f"{invoke_time:.0f}ms")
                return True
            else:
                print_fail("No response generated")
                results.add_test("Agent Invocation", False, error="Empty response")
                return False

        except asyncio.TimeoutError:
            print_fail("Agent timeout (>10s)")
            results.add_test("Agent Invocation", False, error="Timeout")
            return False

    except ImportError as e:
        print_fail(f"Import error: {e}")
        results.add_test("LangGraph Load", False, error=str(e))
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("LangGraph Load", False, error=str(e))
        return False


async def test_frontend_connection(results: DiagnosticResults) -> bool:
    """Test frontend server."""
    print_header("STAGE 5: FRONTEND")

    print_test("Frontend server (http://localhost:3000)")

    try:
        start = time.time()
        response = requests.get("http://localhost:3000", timeout=5)
        latency = (time.time() - start) * 1000

        if response.status_code == 200:
            print_pass("Frontend responding", latency)
            results.add_test("Frontend Server", True, latency)
            return True
        else:
            print_fail(f"HTTP {response.status_code}")
            results.add_test("Frontend Server", False, error=f"HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_warning("Frontend not running")
        print_info("Start with: cd frontend/copilot-demo && npm run dev")
        results.add_test("Frontend Server", False, error="Not running (optional)")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        results.add_test("Frontend Server", False, error=str(e))
        return False


async def main():
    """Run all diagnostics."""
    print_header("LiveKit E2E Diagnostic Tool")
    print_info("Testing all components of the voice pipeline...")
    print_info("This will measure latency and identify broken components.\n")

    results = DiagnosticResults()

    # Stage 1: Infrastructure
    livekit_ok = await check_livekit_server(results)
    llm_ok = await check_llm_server(results)

    if llm_ok:
        await test_llm_inference(results)

    agent_ok = await check_agent_process(results)

    # Stage 2-3: STT/TTS
    await test_stt_model(results)
    await test_tts_model(results)

    # Stage 4: LangGraph
    await test_langgraph_integration(results)

    # Stage 5: Frontend
    await test_frontend_connection(results)

    # Print summary
    all_passed = results.print_summary()

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
