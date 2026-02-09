#!/usr/bin/env python3
"""Test script to verify /chat endpoint bug and fix."""

import requests
import json

def test_chat_endpoint():
    """Test that /chat endpoint works."""
    url = "http://localhost:8000/chat"
    payload = {
        "messages": [
            {"role": "user", "content": "What is 2+2?"}
        ],
        "thread_id": "test-chat-endpoint-001",
        "stream": False
    }

    print(f"Testing POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"\nStatus: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code == 200:
            print("\n✅ SUCCESS: /chat endpoint working")
            return True
        else:
            print(f"\n❌ FAILED: Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_chat_endpoint()
    exit(0 if success else 1)
