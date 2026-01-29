#!/usr/bin/env python3
"""
Simplified LiveKit agent for testing basic connection without STT/TTS complexity.
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("simple-agent")

try:
    from livekit.agents import (
        Agent,
        AgentServer,
        AgentSession,
        JobContext,
        cli,
    )
    from livekit import rtc
    import numpy as np
except ImportError as e:
    logger.error(f"LiveKit agents not installed: {e}")
    sys.exit(1)

# Create server
server = AgentServer()

class SimpleTestAgent(Agent):
    """Minimal test agent that just plays a greeting tone."""
    
    def __init__(self):
        super().__init__(
            instructions="I am a simple test agent that plays a greeting tone.",
        )
        logger.info("🎯 SimpleTestAgent initialized")

    async def on_enter(self):
        """Called when agent joins the session."""
        logger.info(f"🎯 SIMPLE_AGENT: on_enter called for room {self.session.room.name}")
        
        # Just log that we entered - no complex initialization
        logger.info("✅ SIMPLE_AGENT: Successfully entered session")

@server.rtc_session(agent_name="SimpleTestAgent")
async def entrypoint(ctx: JobContext):
    """Simplified entrypoint that just plays a tone."""
    logger.info(f"🎯 SIMPLE_ENTRYPOINT: Called for room {ctx.room.name}")
    
    try:
        # Create minimal session with no STT/TTS
        session = AgentSession()
        
        # Create simple agent
        agent = SimpleTestAgent()
        
        # Start session
        await session.start(agent=agent, room=ctx.room)
        logger.info(f"✅ SIMPLE_SESSION: Started for room {ctx.room.name}")
        
        # Wait a moment for session to establish
        await asyncio.sleep(1)
        
        # Generate simple greeting tone
        logger.info("🔊 SIMPLE_GREETING: Generating test tone...")
        
        try:
            # Create audio source and track
            source = rtc.AudioSource(48000, 1)
            track = rtc.LocalAudioTrack.create_audio_track("simple_greeting", source)
            
            # Publish track
            pub = await ctx.room.local_participant.publish_track(track)
            logger.info("📡 SIMPLE_GREETING: Track published")
            
            # Generate 1 second of 440Hz tone
            duration = 1.0
            sample_rate = 48000
            freq = 440.0
            amplitude = 32767 * 0.2  # 20% volume
            
            total_samples = int(duration * sample_rate)
            t = np.arange(total_samples) / sample_rate
            wave_data = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)
            
            # Convert to bytes
            audio_bytes = wave_data.tobytes()
            
            # Send in 10ms chunks
            chunk_size = 480 * 2  # 10ms at 48kHz, 16-bit
            samples_per_chunk = 480
            
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
            
            logger.info("✅ SIMPLE_GREETING: Tone playback completed")
            
            # Wait before unpublishing
            await asyncio.sleep(0.5)
            await ctx.room.local_participant.unpublish_track(pub.sid)
            logger.info("📡 SIMPLE_GREETING: Track unpublished")
            
        except Exception as audio_error:
            logger.error(f"❌ SIMPLE_GREETING: Audio error: {audio_error}", exc_info=True)
        
        logger.info("🎯 SIMPLE_ENTRYPOINT: Completed successfully")
        
    except Exception as e:
        logger.error(f"❌ SIMPLE_ENTRYPOINT: Failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    print("=" * 60)
    print("Simple LiveKit Test Agent")
    print("=" * 60)
    
    cli.run_app(server)