
import asyncio
import os
import logging
from livekit import rtc, api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulator")

async def main():
    url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    api_key = os.environ.get("LIVEKIT_API_KEY", "devkey")
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "secret")
    room_name = "test-room-verify-4"
    
    logger.info(f"Available API methods: {dir(api)}")


    import requests
    
    logger.info("Dispatching agent...")
    # Generate admin token for dispatch
    grant = api.VideoGrants(room_create=True, room_admin=True, room=room_name)
    admin_token = api.AccessToken(api_key, api_secret) \
        .with_identity("admin-dispatcher") \
        .with_grants(grant) \
        .to_jwt()
        
    try:
        http_url = url.replace("ws://", "http://").replace("wss://", "https://")
        resp = requests.post(
            f"{http_url}/twirp/livekit.AgentDispatchService/CreateDispatch",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"room": room_name, "agent_name": "BestBoxVoiceAgent"}
        )
        logger.info(f"Dispatch response: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Dispatch request failed: {e}")

    logger.info(f"Generating token for {room_name}...")
    token = api.AccessToken(api_key, api_secret) \
        .with_identity("user-simulator") \
        .with_name("User Simulator") \
        .with_grants(api.VideoGrants(room_join=True, room=room_name)) \
        .to_jwt()

    room = rtc.Room()

    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        logger.info(f"✅ Track subscribed: {track.kind} from {participant.identity}")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
             logger.info("🔊 Audio track received! Success!")

    @room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"👤 Participant connected: {participant.identity}")

    logger.info(f"Connecting to {url}...")
    try:
        await room.connect(url, token)
        logger.info(f"Connected to room '{room_name}'")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return

    # Wait for a bit to allow agent to join and publish
    logger.info("Waiting for agent activity (15s)...")
    await asyncio.sleep(15)
    
    await room.disconnect()
    logger.info("Disconnected")

if __name__ == "__main__":
    asyncio.run(main())
