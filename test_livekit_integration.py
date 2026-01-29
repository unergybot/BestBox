#!/usr/bin/env python3
"""
Test LiveKit Voice Integration - Focused Test
"""

import asyncio
import logging
import requests
import json
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_livekit_integration():
    """Test the complete LiveKit voice integration pipeline."""
    
    logger.info("🎯 Testing LiveKit Voice Integration")
    logger.info("=" * 50)
    
    # Test 1: Check LiveKit server health
    try:
        response = requests.get("http://localhost:7880", timeout=5)
        logger.info("✅ LiveKit server is accessible")
    except Exception as e:
        logger.error(f"❌ LiveKit server not accessible: {e}")
        return False
    
    # Test 2: Check agent registration
    try:
        # Create a test room and dispatch agent
        room_name = f"test-room-{int(time.time())}"
        
        dispatch_response = requests.post(
            "http://localhost:3000/api/livekit/dispatch",
            json={"roomName": room_name},
            timeout=10
        )
        
        if dispatch_response.status_code == 200:
            logger.info("✅ Agent dispatch successful")
        else:
            logger.error(f"❌ Agent dispatch failed: {dispatch_response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Agent dispatch error: {e}")
        return False
    
    # Test 3: Check token generation
    try:
        token_response = requests.post(
            "http://localhost:3000/api/livekit/token",
            json={
                "roomName": room_name,
                "participantName": f"test-user-{int(time.time())}"
            },
            timeout=10
        )
        
        if token_response.status_code == 200:
            token_data = token_response.json()
            if "token" in token_data:
                logger.info("✅ Token generation successful")
            else:
                logger.error("❌ Token missing in response")
                return False
        else:
            logger.error(f"❌ Token generation failed: {token_response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Token generation error: {e}")
        return False
    
    # Test 4: Check frontend accessibility
    try:
        frontend_response = requests.get("http://localhost:3000/en/voice", timeout=5)
        if frontend_response.status_code == 200:
            logger.info("✅ Voice page accessible")
        else:
            logger.error(f"❌ Voice page not accessible: {frontend_response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Frontend error: {e}")
        return False
    
    logger.info("🎉 All LiveKit integration tests passed!")
    logger.info("🎙️ Voice integration is ready for testing")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Open http://localhost:3000/en/voice in your browser")
    logger.info("2. Click 'Start Voice Session'")
    logger.info("3. Allow microphone permissions")
    logger.info("4. Listen for the greeting chord progression")
    logger.info("5. Start speaking to test voice interaction")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_livekit_integration())
    exit(0 if success else 1)