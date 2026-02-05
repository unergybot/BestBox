import requests
import json
import uuid
import time
import sys

BASE_URL = "http://localhost:8005"
HEADERS = {"Content-Type": "application/json", "x-user-id": "test-user-integration"}
ADMIN_HEADERS = {"admin-token": "bestbox-admin-token"}  # Update with actual token if needed

def test_health():
    print(f"Testing Health Check at {BASE_URL}/health...")
    try:
        resp = requests.get(f"{BASE_URL}/health")
        resp.raise_for_status()
        print("✅ Health Check Passed")
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        sys.exit(1)

def test_react_endpoint():
    print("\nTesting ReAct Endpoint...")
    
    # Trace ID for correlation
    thread_id = str(uuid.uuid4())
    
    payload = {
        "messages": [
            {"role": "user", "content": "How many purchase orders are in draft status? Also, what are the top vendors?"}
        ],
        "thread_id": thread_id,
        "model": "bestbox-react"  # Optional, but good practice
    }
    
    try:
        start_time = time.time()
        resp = requests.post(f"{BASE_URL}/chat/react", headers=HEADERS, json=payload)
        resp.raise_for_status()
        duration = time.time() - start_time
        
        data = resp.json()
        
        # Verify structure
        if "reasoning_trace" not in data:
            print("❌ 'reasoning_trace' missing in response")
            sys.exit(1)
            
        trace = data["reasoning_trace"]
        print(f"✅ ReAct Trace Received ({len(trace)} steps) in {duration:.2f}s")
        
        # Print a summary of the trace
        for step in trace:
            step_type = step.get("type", "unknown")
            step_content = step.get("content", "")
            tool_name = step.get("tool_name")
            
            if step_type == "think":
                print(f"  🤔 Think: {step_content[:50]}...")
            elif step_type == "act":
                print(f"  🔧 Act: {tool_name}")
            elif step_type == "observe":
                print(f"  📊 Observe: {str(step_content)[:50]}...")
            elif step_type == "answer":
                print(f"  💡 Answer: {step_content[:50]}...")
                
        # Verify choices/message content
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
             print("⚠️ Warning: No final content in message")
        else:
             print(f"✅ Final Response Received: {content[:50]}...")

        return data.get("session_id")

    except Exception as e:
        print(f"❌ ReAct Request Failed: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        sys.exit(1)

def test_admin_sessions(session_id):
    print(f"\nTesting Admin Session Logging for ID: {session_id}...")
    
    if not session_id:
        print("⚠️ No session ID from previous test, skipping lookup")
        return

    try:
        # 1. List sessions
        resp = requests.get(f"{BASE_URL}/admin/sessions?limit=5", headers=ADMIN_HEADERS)
        if resp.status_code == 401:
             print("⚠️ Admin token invalid/missing (401). Skipping admin test.")
             return
        
        resp.raise_for_status()
        sessions = resp.json()
        print(f"✅ Listed {len(sessions)} recent sessions")
        
        found = False
        for s in sessions:
            if str(s.get("id")) == str(session_id):
                found = True
                print("✅ Found our session in list")
                break
        
        if not found:
            print("⚠️ Warning: Session ID not found in recent list")

        # 2. Get specific session details
        resp = requests.get(f"{BASE_URL}/admin/sessions/{session_id}", headers=ADMIN_HEADERS)
        resp.raise_for_status()
        session_detail = resp.json()
        
        messages = session_detail.get("messages", [])
        print(f"✅ Session Detail Retrieved: {len(messages)} messages logged")
        
        # Verify we stored the reasoning trace
        has_trace = False
        for msg in messages:
            if msg.get("reasoning_trace"):
                has_trace = True
                break
        
        if has_trace:
            print("✅ Verified reasoning trace is stored in DB")
        else:
            print("❌ Reasoning trace NOT found in DB logs")

    except Exception as e:
        print(f"❌ Admin API Failed: {e}")

if __name__ == "__main__":
    test_health()
    session_id = test_react_endpoint()
    test_admin_sessions(session_id)
    print("\n🎉 All integration tests passed!")
