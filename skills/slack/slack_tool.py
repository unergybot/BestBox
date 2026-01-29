
import os
import argparse
import sys
import json
from typing import Optional, Dict, Any

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print(json.dumps({"ok": False, "error": "slack_sdk module not found. Please install it."}))
    sys.exit(1)

def get_client() -> WebClient:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print(json.dumps({"ok": False, "error": "SLACK_BOT_TOKEN environment variable not set."}))
        sys.exit(1)
    return WebClient(token=token)

def send_message(channel: str, text: str) -> None:
    client = get_client()
    try:
        response = client.chat_postMessage(channel=channel, text=text)
        print(json.dumps({
            "ok": True, 
            "ts": response["ts"], 
            "channel": response["channel"],
            "message": "Message sent successfully"
        }))
    except SlackApiError as e:
        print(json.dumps({"ok": False, "error": f"Slack API error: {e.response['error']}"}))

def list_channels(limit: int = 20) -> None:
    client = get_client()
    try:
        response = client.conversations_list(limit=limit, types="public_channel,private_channel")
        channels = [
            {"id": c["id"], "name": c["name"], "is_member": c["is_member"]} 
            for c in response.get("channels", [])
        ]
        print(json.dumps({"ok": True, "channels": channels}))
    except SlackApiError as e:
        print(json.dumps({"ok": False, "error": f"Slack API error: {e.response['error']}"}))

def read_history(channel: str, limit: int = 10) -> None:
    client = get_client()
    try:
        response = client.conversations_history(channel=channel, limit=limit)
        messages = response.get("messages", [])
        print(json.dumps({"ok": True, "messages": messages}))
    except SlackApiError as e:
        print(json.dumps({"ok": False, "error": f"Slack API error: {e.response['error']}"}))

def main():
    parser = argparse.ArgumentParser(description="Slack Skill Tool")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # Send Message
    send_parser = subparsers.add_parser("send", help="Send a message")
    send_parser.add_argument("--channel", required=True, help="Channel ID or name")
    send_parser.add_argument("--text", required=True, help="Message text")

    # List Channels
    list_parser = subparsers.add_parser("list-channels", help="List channels")
    list_parser.add_argument("--limit", type=int, default=20, help="Limit number of channels")

    # Read History
    history_parser = subparsers.add_parser("history", help="Read channel history")
    history_parser.add_argument("--channel", required=True, help="Channel ID or name")
    history_parser.add_argument("--limit", type=int, default=10, help="Limit number of messages")

    args = parser.parse_args()

    if args.action == "send":
        send_message(args.channel, args.text)
    elif args.action == "list-channels":
        list_channels(args.limit)
    elif args.action == "history":
        read_history(args.channel, args.limit)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
