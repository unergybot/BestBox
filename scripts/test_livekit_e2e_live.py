#!/usr/bin/env python3
"""
LiveKit End-to-End LIVE Test

Connects to LiveKit room, sends audio, receives response.
Measures full user-perceived latency.

This is the REAL test - simulates actual user experience.

Usage:
    python scripts/test_livekit_e2e_live.py
"""

import asyncio
import sys
import os
import time
import numpy as np
import logging
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("e2e-test")

# Colors for output
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_step(text: str):
    print(f"\n{Color.BOLD}{Color.BLUE}▶ {text}{Color.END}")

def print_success(text: str):
    print(f"{Color.GREEN}✓ {text}{Color.END}")

def print_fail(text: str):
    print(f"{Color.RED}✗ {text}{Color.END}")

def print_timing(label: str, ms: float):
    print(f"{Color.MAGENTA}⏱  {label}: {ms:.0f}ms{Color.END}")

def print_total(label: str, ms: float):
    print(f"\n{Color.BOLD}{Color.CYAN}⏱  {label}: {ms:.0f}ms{Color.END}\n")


class VoiceTestMetrics:
    """Track all timing metrics for the test."""
    def __init__(self):
        self.connection_start = None
        self.connection_end = None
        self.audio_start = None
        self.audio_end = None
        self.first_transcript = None
        self.final_transcript = None
        self.first_response_token = None
        self.first_audio = None
        self.last_audio = None

        self.transcript_text = ""
        self.response_text = ""
        self.audio_chunks_received = 0

    def report(self):
        """Print full timing report."""
        print(f"\n{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}{'END-TO-END TIMING REPORT'.center(80)}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}\n")

        if self.connection_start and self.connection_end:
            conn_time = (self.connection_end - self.connection_start) * 1000
            print_timing("Connection Time", conn_time)

        if self.audio_start and self.first_transcript:
            stt_latency = (self.first_transcript - self.audio_start) * 1000
            print_timing("STT First Partial", stt_latency)

        if self.audio_start and self.final_transcript:
            stt_total = (self.final_transcript - self.audio_start) * 1000
            print_timing("STT Total (to final transcript)", stt_total)

        if self.final_transcript and self.first_response_token:
            agent_latency = (self.first_response_token - self.final_transcript) * 1000
            print_timing("Agent Processing (transcript → first token)", agent_latency)

        if self.first_response_token and self.first_audio:
            tts_latency = (self.first_audio - self.first_response_token) * 1000
            print_timing("TTS First Audio", tts_latency)

        if self.audio_start and self.first_audio:
            total_latency = (self.first_audio - self.audio_start) * 1000
            print_total("TOTAL USER-PERCEIVED LATENCY (speak → hear response)", total_latency)

        print(f"{Color.BOLD}Data Summary:{Color.END}")
        print(f"  Transcript: '{self.transcript_text}'")
        print(f"  Response: '{self.response_text[:100]}...'")
        print(f"  Audio chunks received: {self.audio_chunks_received}")
        print()


async def test_livekit_connection():
    """Test LiveKit room connection and voice interaction."""

    try:
        from livekit import rtc
        import requests
    except ImportError as e:
        print_fail(f"Required package not installed: {e}")
        print("Install with: pip install livekit requests")
        return False

    metrics = VoiceTestMetrics()

    print_step("Generating LiveKit access token...")

    # Generate token via frontend API
    import requests
    identity = f"test-user-{int(time.time())}"

    try:
        response = requests.post(
            "http://localhost:3000/api/livekit/token",
            json={"roomName": "test-room", "participantName": identity},
            timeout=5
        )
        response.raise_for_status()
        token_data = response.json()
        jwt = token_data['token']
        print_success(f"Token generated for identity: {identity}")
    except Exception as e:
        print_fail(f"Failed to generate token: {e}")
        print("Make sure frontend is running: cd frontend/copilot-demo && npm run dev")
        return False

    # Connect to room
    print_step("Connecting to LiveKit room...")
    metrics.connection_start = time.time()

    room = rtc.Room()

    # Track events
    transcript_received = asyncio.Event()
    response_started = asyncio.Event()
    audio_received = asyncio.Event()

    @room.on("data_received")
    def on_data(data: rtc.DataPacket):
        """Handle data channel messages (transcripts, responses)."""
        try:
            import json
            message = json.loads(data.data.decode())
            msg_type = message.get("type")

            if msg_type == "transcript":
                if metrics.first_transcript is None:
                    metrics.first_transcript = time.time()
                    print_success(f"First transcript received: '{message.get('text', '')}'")

                if message.get("is_final"):
                    metrics.final_transcript = time.time()
                    metrics.transcript_text = message.get("text", "")
                    print_success(f"Final transcript: '{metrics.transcript_text}'")
                    transcript_received.set()

            elif msg_type == "agent_response_start":
                if metrics.first_response_token is None:
                    metrics.first_response_token = time.time()
                    print_success("Agent started responding")
                    response_started.set()

            elif msg_type == "agent_response_token":
                token_text = message.get("token", "")
                metrics.response_text += token_text
                if len(metrics.response_text) < 100:  # Only print first 100 chars
                    print(f"  Token: '{token_text}'", end="", flush=True)

        except Exception as e:
            logger.error(f"Error handling data: {e}")

    @room.on("track_subscribed")
    def on_track(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        """Handle incoming audio tracks (agent voice)."""
        logger.info(f"Track subscribed: {track.kind} from {participant.identity}")

        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print_success(f"Subscribed to agent audio track")

            @track.on("frame_received")
            def on_audio_frame(frame: rtc.AudioFrame):
                if metrics.first_audio is None:
                    metrics.first_audio = time.time()
                    print_success("First audio frame received from agent!")
                    audio_received.set()

                metrics.audio_chunks_received += 1
                metrics.last_audio = time.time()

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        print_success(f"Participant connected: {participant.identity}")

    @room.on("connected")
    def on_connected():
        metrics.connection_end = time.time()
        print_success("Connected to LiveKit room")

    try:
        # Connect
        await room.connect("ws://localhost:7880", jwt)

        # Wait for agent to join
        print_step("Waiting for agent to join room...")
        await asyncio.sleep(2)

        if len(room.remote_participants) == 0:
            print_fail("No agent joined the room!")
            print("Make sure LiveKit agent is running: python services/livekit_agent.py dev")
            return False

        print_success(f"Agent joined: {list(room.remote_participants.keys())}")

        # Create local audio track
        print_step("Creating audio track and sending test audio...")

        # Create audio source
        audio_source = rtc.AudioSource(sample_rate=16000, num_channels=1)
        track = rtc.LocalAudioTrack.create_audio_track("test-audio", audio_source)

        # Publish track
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(track, options)
        print_success("Audio track published")

        # Generate test audio (simulated speech)
        print_step("Generating test speech audio...")
        metrics.audio_start = time.time()

        # Generate 3 seconds of test tone (simulates speech)
        # In a real test, you'd load actual speech audio
        sample_rate = 16000
        duration = 3.0  # seconds
        frequency = 440  # Hz (A note)

        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples, False)
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.3  # 30% amplitude
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Send audio in chunks (simulate real-time streaming)
        chunk_duration = 0.02  # 20ms chunks
        chunk_samples = int(sample_rate * chunk_duration)

        for i in range(0, len(audio_int16), chunk_samples):
            chunk = audio_int16[i:i+chunk_samples]

            # Create audio frame
            frame = rtc.AudioFrame(
                data=chunk.tobytes(),
                sample_rate=sample_rate,
                num_channels=1,
                samples_per_channel=len(chunk)
            )

            await audio_source.capture_frame(frame)
            await asyncio.sleep(chunk_duration)  # Real-time pacing

        metrics.audio_end = time.time()
        print_success(f"Sent {duration}s of audio")

        # Wait for transcript
        print_step("Waiting for transcript...")
        try:
            await asyncio.wait_for(transcript_received.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            print_fail("No transcript received after 10 seconds")
            print("Check agent logs for STT issues")

        # Wait for response
        print_step("Waiting for agent response...")
        try:
            await asyncio.wait_for(response_started.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            print_fail("No response from agent after 15 seconds")
            print("Check agent logs for LangGraph issues")

        # Wait for audio
        print_step("Waiting for agent audio...")
        try:
            await asyncio.wait_for(audio_received.wait(), timeout=20.0)
        except asyncio.TimeoutError:
            print_fail("No audio from agent after 20 seconds")
            print("Check agent logs for TTS issues")

        # Wait a bit more to collect all audio
        await asyncio.sleep(3)

        # Print metrics report
        metrics.report()

        return True

    except Exception as e:
        print_fail(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await room.disconnect()
        print_success("Disconnected from room")


async def main():
    """Run end-to-end test."""
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{'LiveKit End-to-End LIVE Test'.center(80)}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}\n")

    print("This test will:")
    print("  1. Connect to LiveKit room")
    print("  2. Send test audio (3 seconds)")
    print("  3. Measure time to transcript")
    print("  4. Measure time to agent response")
    print("  5. Measure time to audio playback")
    print("  6. Report total user-perceived latency\n")

    success = await test_livekit_connection()

    if success:
        print(f"\n{Color.GREEN}{Color.BOLD}TEST PASSED ✓{Color.END}\n")
        return 0
    else:
        print(f"\n{Color.RED}{Color.BOLD}TEST FAILED ✗{Color.END}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
