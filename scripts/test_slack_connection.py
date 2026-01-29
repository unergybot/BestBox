import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tools.slack import SlackTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_slack():
    print("🤖 Initializing SlackTool...")
    tool = SlackTool()
    
    check = tool._check_client()
    if not check["ok"]:
        print(f"❌ Initialization failed: {check.get('error')}")
        print("Did you export SLACK_BOT_TOKEN?")
        return

    print("✅ SlackTool initialized.")

    try:
        # 1. List Channels (using underlying client directly for this test)
        print("\n🔍 Listing channels bot has access to...")
        response = tool.client.conversations_list(types="public_channel,private_channel")
        channels = response.get("channels", [])
        
        if not channels:
            print("⚠️ No channels found. Invite the bot to a channel first!")
            return

        print(f"Found {len(channels)} channels:")
        target_channel = None
        for ch in channels:
            print(f" - #{ch['name']} (ID: {ch['id']})")
            if not target_channel and not ch["is_archived"]:
                target_channel = ch

        if target_channel:
            # 2. Send Message
            print(f"\nce📩 Sending test message to #{target_channel['name']} ({target_channel['id']})...")
            result = tool.chat_postMessage(target_channel["id"], "Hello from BestBox! 🤖")
            
            if result["ok"]:
                print(f"✅ Message sent successfully! Timestamp: {result['ts']}")
            else:
                print(f"❌ Failed to send message: {result.get('error')}")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    test_slack()
