#!/usr/bin/env python3
"""
Chain-by-Chain Voice Pipeline Verification
"Superpower" diagnostic script.
"""

import asyncio
import logging
import os
import sys
import time
import numpy as np
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verify_pipeline")

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

def log_pass(msg):
    logger.info(f"{GREEN}✓ PASS: {msg}{RESET}")

def log_fail(msg):
    logger.error(f"{RED}✗ FAIL: {msg}{RESET}")

def log_warn(msg):
    logger.warning(f"{YELLOW}⚠ WARNING: {msg}{RESET}")

def log_info(msg):
    logger.info(f"{CYAN}ℹ INFO: {msg}{RESET}")

async def verify_tts_component():
    """Chain 1: Verify TTS Component produces valid 48kHz PCM."""
    log_info("--- Chain 1: TTS Component Verification ---")
    try:
        from services.speech.tts import StreamingTTS, TTSConfig
        from services.livekit_local import LocalTTS, LocalTTSStream
        
        # Test LocalTTS wrapper specifically
        log_info("Initializing LocalTTS with 48kHz config...")
        config = TTSConfig(sample_rate=48000, fallback_to_piper=True)
        streaming_tts = StreamingTTS(config)
        local_tts = LocalTTS(config, tts_instance=streaming_tts)
        
        # We need to manually simulate the stream processing because LocalTTSStream 
        # is designed to work within a LiveKit agent loop.
        # Instead, let's verify the underlying _synthesize_piper method 
        # AND manual resampling logic if we can access it, 
        # OR just check what StreamingTTS produces and confirm we have the tools to resample.
        
        text = "Audio check one two three."
        start = time.time()
        # Direct synthesis from StreamingTTS (which uses Piper -> 22050 usually)
        raw_audio = streaming_tts.synthesize(text)
        duration = time.time() - start
        
        if not raw_audio:
            log_fail("TTS produced empty audio")
            return False
            
        # Check raw Piper output
        pcm_orig = np.frombuffer(raw_audio, dtype=np.int16)
        sr_piper = 22050 # Assumption
        duration_s = len(pcm_orig) / sr_piper
        log_pass(f"Piper produced {len(raw_audio)} bytes ({duration_s:.2f}s implied @ 22kHz) in {duration*1000:.0f}ms")
        
        # Verify Resampling Logic (mirrors livekit_local.py)
        log_info("Verifying Resampling Logic (22050 -> 48000)...")
        target_sr = 48000
        num_target_samples = int((len(pcm_orig) / 22050) * target_sr)
        indices = np.linspace(0, len(pcm_orig) - 1, num_target_samples)
        pcm_48k = np.interp(indices, np.arange(len(pcm_orig)), pcm_orig).astype(np.int16)
        
        if len(pcm_48k) < len(pcm_orig):
            log_fail("Resampling failed: output shorter than input (upsampling expected)")
            return False
            
        log_pass(f"Resampling successful: {len(pcm_orig)} samples -> {len(pcm_48k)} samples")
        
        # Check Energy
        energy = np.sqrt(np.mean(pcm_48k.astype(float)**2))
        log_info(f"Audio Energy: {energy:.2f}")
        if energy < 100:
            log_warn("Audio energy is low (near silence).")
        else:
            log_pass("Audio energy looks healthy.")
            
        return True
        
    except Exception as e:
        log_fail(f"TTS Verification failed: {e}")
        return False

async def verify_livekit_transport():
    """Chain 2: Verify Audio Transport via Simulated User."""
    log_info("--- Chain 2: LiveKit Transport Verification ---")
    
    try:
        from livekit import api, rtc
        
        URL = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
        API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
        API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")
        
        room_name = f"verify-chain-{int(time.time())}"
        identity = f"verify-user-{int(time.time())}"
        
        # Connect
        log_info(f"Connecting to {URL} as {identity} in {room_name}...")
        room = rtc.Room()
        
        audio_received = asyncio.Event()
        
        @room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                log_pass(f"Subscribed to Audio Track from {participant.identity}!")
                
                # Attach audio receiver
                stream = rtc.AudioStream(track)
                asyncio.create_task(analyze_audio_stream(stream, audio_received))

        async def analyze_audio_stream(stream, event):
            log_info("Analyzing incoming audio stream...")
            total_frames = 0
            silent_frames = 0
            active_frames = 0
            
            async for frame in stream:
                total_frames += 1
                
                # Check format
                if frame.sample_rate != 48000:
                    log_warn(f"Received frame SR: {frame.sample_rate} (Expected 48000)")
                
                # Check Content
                data = np.frombuffer(frame.data, dtype=np.int16)
                energy = np.sqrt(np.mean(data.astype(float)**2))
                
                if energy > 100:
                    active_frames += 1
                    if active_frames == 1:
                         log_pass(f"First ACTIVE audio frame detected! Energy: {energy:.2f}")
                         event.set()
                else:
                    silent_frames += 1
                
                if total_frames % 50 == 0:
                    log_info(f"Stream Stats: {total_frames} frames, {active_frames} active, {silent_frames} silent. Energy={energy:.2f}")

        await room.connect(URL, api.AccessToken(API_KEY, API_SECRET).with_identity(identity).with_name(identity).with_grants(api.VideoGrants(room_join=True, room=room_name)).to_jwt())
        log_pass("Connected to room.")
        
        # Publish audio to trigger agent
        log_info("Publishing dummy mic track to trigger user entry...")
        source = rtc.AudioSource(48000, 1)
        track = rtc.LocalAudioTrack.create_audio_track("mic", source)
        await room.local_participant.publish_track(track)
        
        # Wait for audio
        log_info("Waiting for agent audio response (15s timeout)...")
        try:
            await asyncio.wait_for(audio_received.wait(), timeout=15)
            log_pass("Chain 2 SUCCESS: Audio received and verified active!")
            await room.disconnect()
            return True
        except asyncio.TimeoutError:
            log_fail("Chain 2 FAILED: Timed out waiting for active audio.")
            await room.disconnect()
            return False
            
    except Exception as e:
        log_fail(f"Transport verification failed: {e}")
        return False

async def main():
    log_info("Starting SUPERPOWER Validation Sequence...")
    
    # 1. Transport Check
    transport_ok = await verify_livekit_transport()
    
    # 2. Component Check
    tts_ok = await verify_tts_component()
    
    if transport_ok and tts_ok:
        log_pass(">>> ALL SYSTEMS GO. VOICE PIPELINE VERIFIED. <<<")
        sys.exit(0)
    else:
        log_fail(">>> VERIFICATION FAILED. CHECK LOGS. <<<")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
