
import asyncio
import os
import sys
import logging
import uuid
from livekit import api, rtc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verify_agent")

async def test_agent_audio():
    logger.info("🚀 Starting Agent Audio Verification Test")
    
    # 1. Generate Token
    room_name = f"test-room-{uuid.uuid4().hex[:6]}"
    identity = "tester-bot"
    
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY", "devkey"),
        os.getenv("LIVEKIT_API_SECRET", "secret")
    ).with_identity(identity) \
    .with_name("Tester Bot") \
    .with_grants(api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True
    )).to_jwt()
    
    logger.info(f"🔑 Token generated for room: {room_name}")

    # 2. Connect to Room
    room = rtc.Room()
    
    audio_received_event = asyncio.Event()
    
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        logger.info(f"✅ Track Subscribed: {track.kind} from {participant.identity}")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info("🎧 Audio track detected! Waiting for audio data...")
            asyncio.create_task(monitor_audio(track))

    async def monitor_audio(track):
        audio_stream = rtc.AudioStream(track)
        async for frame in audio_stream:
            # Check if frame has energy/content
            logger.info(f"🔊 Audio Frame Received! (Samples: {len(frame.data)})")
            audio_received_event.set()
            break # One frame is enough to prove flow

    try:
        logger.info("Connecting to LiveKit server...")
        await room.connect("ws://localhost:7880", token)
        logger.info("✅ Connected to room!")
        
        # 3. Wait for Agent (~45s timeout)
        logger.info(f"⏳ Waiting for audio (45s timeout) in {room_name}...")
        try:
            await asyncio.wait_for(audio_received_event.wait(), timeout=45.0)
            logger.info("🎉 SUCCESS: Audio received from Agent!")
            print("TEST_RESULT: PASS")
        except asyncio.TimeoutError:
            logger.error("❌ FAILURE: Timed out waiting for audio.")
            print("TEST_RESULT: FAIL")
            # Debug info
            # Handle API variations
            parts = getattr(room, 'remote_participants', {})
            logger.info(f"Participants in room: {[p.identity for p in parts.values()]}")
            
    except Exception as e:
        logger.error(f"❌ Test Failed with Exception: {e}")
        print("TEST_RESULT: FAIL")
    finally:
        await room.disconnect()
        logger.info("Disconnected.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_agent_audio())
