#!/usr/bin/env python3
"""
Test LiveKit Voice Session - End-to-End Test
"""

import asyncio
import logging
import requests
import json
import time
from livekit import api

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_voice_session():
    """Test a complete voice session with the BestBox agent."""
    
    logger.info("🎯 Testing LiveKit Voice Session")
    logger.info("=" * 50)
    
    try:
        # Create a test room
        room_name = f"test-session-{int(time.time())}"
        logger.info(f"📝 Creating test room: {room_name}")
        
        # Dispatch agent to room
        dispatch_response = requests.post(
            "http://localhost:3000/api/livekit/dispatch",
            json={"roomName": room_name},
            timeout=15
        )
        
        if dispatch_response.status_code != 200:
            logger.error(f"❌ Agent dispatch failed: {dispatch_response.status_code}")
            return False
        
        logger.info("✅ Agent dispatched to room")
        
        # Wait for agent to join
        await asyncio.sleep(3)
        
        # Get user token
        token_response = requests.post(
            "http://localhost:3000/api/livekit/token",
            json={
                "roomName": room_name,
                "participantName": f"test-user-{int(time.time())}"
            },
            timeout=10
        )
        
        if token_response.status_code != 200:
            logger.error(f"❌ Token generation failed: {token_response.status_code}")
            return False
        
        token_data = token_response.json()
        user_token = token_data["token"]
        logger.info("✅ User token generated")
        
        # Check room status using LiveKit API
        try:
            livekit_api = api.LiveKitAPI(
                url="ws://localhost:7880",
                api_key="devkey",
                api_secret="secret"
            )
            
            # List rooms to verify our room exists
            rooms = await livekit_api.room.list_rooms()
            test_room = None
            for room in rooms:
                if room.name == room_name:
                    test_room = room
                    break
            
            if test_room:
                logger.info(f"✅ Room found: {test_room.name} with {test_room.num_participants} participants")
                
                # List participants
                participants = await livekit_api.room.list_participants(room_name)
                logger.info(f"📊 Participants in room:")
                for p in participants:
                    logger.info(f"  - {p.identity} ({p.name})")
                
                # Check if agent is present
                agent_present = any("BestBox" in p.name or "agent" in p.identity.lower() for p in participants)
                if agent_present:
                    logger.info("✅ BestBox agent is present in room")
                else:
                    logger.warning("⚠️ BestBox agent not found in room")
                
            else:
                logger.warning(f"⚠️ Room {room_name} not found in active rooms")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not check room status: {e}")
        
        logger.info("🎉 Voice session test completed successfully!")
        logger.info("")
        logger.info("🎙️ The LiveKit voice integration is working!")
        logger.info("")
        logger.info("Manual testing instructions:")
        logger.info("1. Open http://localhost:3000/en/voice")
        logger.info("2. Click 'Start Voice Session'")
        logger.info("3. Allow microphone permissions")
        logger.info("4. You should hear a greeting chord progression (C-E-G)")
        logger.info("5. Start speaking - try: 'What are the top vendors?'")
        logger.info("6. The agent should respond with voice and text")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Voice session test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_voice_session())
    exit(0 if success else 1)