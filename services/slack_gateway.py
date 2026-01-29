
import os
import logging
import asyncio
import aiohttp
import json
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("slack_gateway")

# Load environment variables
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
AGENT_API_URL = os.environ.get("AGENT_API_URL", "http://localhost:8000/v1/chat/completions")

if not SLACK_BOT_TOKEN:
    logger.error("SLACK_BOT_TOKEN is not set")
if not SLACK_APP_TOKEN:
    logger.error("SLACK_APP_TOKEN is not set")

# Initialize Bolt App
app = AsyncApp(token=SLACK_BOT_TOKEN)

@app.event("app_mention")
async def handle_app_mentions(event, say):
    """Handle @mentions"""
    await process_message(event, say)

@app.event("message")
async def handle_message_events(event, say):
    """Handle direct messages and channel messages"""
    if event.get("subtype") is None or event.get("subtype") == "file_share":
        await process_message(event, say)

async def process_message(event, say):
    user_id = event.get("user")
    channel_id = event.get("channel")
    text = event.get("text", "")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts", ts) # Reply in thread if it's already a thread, else start one

    logger.info(f"Received message from {user_id} in {channel_id}: {text}")

    # Prevent bot loops
    if event.get("bot_id"):
        return

    # Notify via emoji that we are processing
    try:
        await app.client.reactions_add(
            channel=channel_id,
            timestamp=ts,
            name="eyes"
        )
    except Exception as e:
        logger.warning(f"Failed to add reaction: {e}")

    try:
        # Call Agent API
        async with aiohttp.ClientSession() as session:
            payload = {
                "messages": [
                    {"role": "user", "content": text}
                ],
                "model": "bestbox-agent",
                "stream": False,
                # Use thread_ts as session_id to maintain context per thread
                "thread_id": f"slack-{channel_id}-{thread_ts}"
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-user-id": f"slack:{user_id}"
            }

            async with session.post(AGENT_API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response_text = data["choices"][0]["message"]["content"]
                    
                    # Send response back to Slack
                    await say(text=response_text, thread_ts=thread_ts)
                    
                    # Update reaction to success
                    try:
                        await app.client.reactions_remove(channel=channel_id, timestamp=ts, name="eyes")
                        await app.client.reactions_add(channel=channel_id, timestamp=ts, name="white_check_mark")
                    except:
                        pass
                else:
                    error_text = await resp.text()
                    logger.error(f"Agent API error: {resp.status} - {error_text}")
                    await say(text=f"Check your connection to BestBox Agent API. Error: {resp.status}", thread_ts=thread_ts)
                    
                    try:
                        await app.client.reactions_remove(channel=channel_id, timestamp=ts, name="eyes")
                        await app.client.reactions_add(channel=channel_id, timestamp=ts, name="warning")
                    except:
                        pass

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await say(text=f"I encountered an internal error: {str(e)}", thread_ts=thread_ts)
        try:
            await app.client.reactions_remove(channel=channel_id, timestamp=ts, name="eyes")
            await app.client.reactions_add(channel=channel_id, timestamp=ts, name="x")
        except:
            pass

async def main():
    if not SLACK_APP_TOKEN:
        logger.error("Cannot start Socket Mode without SLACK_APP_TOKEN")
        return

    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    logger.info("⚡️ BestBox Slack Gateway is running!")
    await handler.start_async()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Check configuration and exit")
    args = parser.parse_args()

    if args.dry_run:
        if SLACK_BOT_TOKEN and SLACK_APP_TOKEN:
            print("Configuration OK: Tokens present.")
            # Optionally check connectivity here
        else:
            print("Configuration Error: Missing tokens.")
            exit(1)
    else:
        asyncio.run(main())
