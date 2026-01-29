#!/usr/bin/env python3
"""
Simple LiveKit agent test - just publishes test audio on connection
This bypasses all STT/LLM/TTS to test if LiveKit publishing works
"""

import asyncio
import logging
import numpy as np
from livekit.agents import AgentServer, JobContext, cli
from livekit import rtc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-agent")

server = AgentServer()

@server.rtc_session(agent_name="BestBoxVoiceAgent")  # MUST match dispatch API name!
async def entrypoint(ctx: JobContext):
    """Test agent that just publishes audio."""
    logger.info("=" * 80)
    
    # Connect to the room
    logger.info(f"🔗 Connecting to room: {ctx.room.name}")
    await ctx.connect()
    logger.info("🔊 TEST AGENT CONNECTED TO ROOM!")
    logger.info(f"Room: {ctx.room.name}")
    logger.info("=" * 80)

    # Room is ready when entrypoint is called
    logger.info("📢 Publishing test audio...")

    # Generate test tone (440Hz for 2 seconds)
    sample_rate = 48000  # LiveKit expects 48kHz
    duration = 2.0
    frequency = 440  # A note

    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * frequency * t) * 0.3
    audio_int16 = (audio_data * 32767).astype(np.int16)

    # Create audio source and track
    source = rtc.AudioSource(sample_rate=sample_rate, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("test-audio", source)

    # Publish track
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    publication = await ctx.room.local_participant.publish_track(track, options)
    logger.info(f"✅ Track published: {publication.sid}")

    # Send audio in chunks
    chunk_size = int(sample_rate * 0.02)  # 20ms chunks

    for i in range(0, len(audio_int16), chunk_size):
        chunk = audio_int16[i:i+chunk_size]

        frame = rtc.AudioFrame(
            data=chunk.tobytes(),
            sample_rate=sample_rate,
            num_channels=1,
            samples_per_channel=len(chunk)
        )

        await source.capture_frame(frame)
        await asyncio.sleep(0.02)  # 20ms delay

    logger.info("✅ Test audio sent! If you heard a 440Hz tone for 2 seconds, LiveKit publishing works!")
    logger.info("💡 If you heard nothing, the problem is in LiveKit setup or browser audio")

    # Keep agent alive
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    print("=" * 60)
    print("SIMPLE LIVEKIT TEST AGENT")
    print("=" * 60)
    print("This agent will:")
    print("  1. Connect to LiveKit room")
    print("  2. Publish a 440Hz test tone for 2 seconds")
    print("  3. If you hear it → LiveKit works!")
    print("  4. If silence → LiveKit/browser issue")
    print("=" * 60)

    cli.run_app(server)
