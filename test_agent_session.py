#!/usr/bin/env python3
"""
Test script to trigger a LiveKit agent session and monitor the logs.
"""

import asyncio
import requests
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent_session():
    """Test creating a room and dispatching an agent."""
    
    # Create a unique room name
    room_name = f"test-debug-{int(time.time())}"
    base_url = "http://localhost:3000"
    
    logger.info(f"🚀 Testing agent session with room: {room_name}")
    
    try:
        # Step 1: Dispatch agent to room
        logger.info("📡 Dispatching agent to room...")
        dispatch_response = requests.post(
            f"{base_url}/api/livekit/dispatch",
            json={"roomName": room_name},
            timeout=15
        )
        
        if dispatch_response.status_code == 200:
            logger.info("✅ Agent dispatch successful")
            logger.info(f"Response: {dispatch_response.json()}")
        else:
            logger.error(f"❌ Agent dispatch failed: {dispatch_response.status_code}")
            logger.error(f"Response: {dispatch_response.text}")
            return
        
        # Step 2: Wait for agent to join
        logger.info("⏳ Waiting for agent to join room...")
        await asyncio.sleep(3)
        
        # Step 3: Get user token
        logger.info("🎫 Getting user token...")
        token_response = requests.post(
            f"{base_url}/api/livekit/token",
            json={
                "roomName": room_name,
                "participantName": "test-user-debug"
            },
            timeout=10
        )
        
        if token_response.status_code == 200:
            token_data = token_response.json()
            logger.info("✅ Token generation successful")
            logger.info(f"Token: {token_data['token'][:50]}...")
        else:
            logger.error(f"❌ Token generation failed: {token_response.status_code}")
            logger.error(f"Response: {token_response.text}")
            return
        
        # Step 4: Simulate connection (we can't actually connect without WebRTC client)
        logger.info("🔗 Session setup complete. Check agent logs for entrypoint activity.")
        logger.info(f"Room: {room_name}")
        logger.info(f"Agent should be active in the room now.")
        
        # Wait a bit to see if agent logs show activity
        logger.info("⏳ Waiting 10 seconds to monitor agent activity...")
        await asyncio.sleep(10)
        
        logger.info("✅ Test completed. Check agent process logs for session details.")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent_session())