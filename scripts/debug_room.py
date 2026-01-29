
import asyncio
import os
from livekit import api

LIVEKIT_URL = "ws://localhost:7880"
LIVEKIT_API_KEY = "devkey"
LIVEKIT_API_SECRET = "secret"

async def main():
    print(f"Connecting to {LIVEKIT_URL} as a user...")
    try:
        lkapi = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        
        # List rooms and participants
        rooms = await lkapi.room.list_rooms(api.ListRoomsRequest())
        print(f"Rooms found: {len(rooms.rooms)}")
        for room in rooms.rooms:
            print(f"Room: {room.name} (SID: {room.sid})")
            participants = await lkapi.room.list_participants(api.ListParticipantsRequest(room=room.name))
            print(f"  Participants: {len(participants.participants)}")
            for p in participants.participants:
                print(f"    - Identity: {p.identity}")
                print(f"      Kind: {p.kind}")
                
        await lkapi.aclose()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
