
import os
import argparse
import sys
import json
import asyncio
from typing import Optional, Dict, Any

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    print(json.dumps({"ok": False, "error": "python-telegram-bot module not found. Please install it."}))
    sys.exit(1)

async def get_bot() -> Bot:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print(json.dumps({"ok": False, "error": "TELEGRAM_BOT_TOKEN environment variable not set."}))
        sys.exit(1)
    return Bot(token=token)

async def send_message(chat_id: str, text: str) -> None:
    bot = await get_bot()
    try:
        message = await bot.send_message(chat_id=chat_id, text=text)
        print(json.dumps({
            "ok": True, 
            "message_id": message.message_id, 
            "chat_id": message.chat.id,
            "message": "Message sent successfully"
        }))
    except TelegramError as e:
        print(json.dumps({"ok": False, "error": f"Telegram API error: {e}"}))

async def check_updates() -> None:
    bot = await get_bot()
    try:
        updates = await bot.get_updates()
        result = []
        for u in updates:
            if u.message:
                result.append({
                    "update_id": u.update_id,
                    "chat_id": u.message.chat.id,
                    "username": u.message.from_user.username,
                    "text": u.message.text
                })
        print(json.dumps({"ok": True, "updates": result}))
    except TelegramError as e:
        print(json.dumps({"ok": False, "error": f"Telegram API error: {e}"}))

def main():
    parser = argparse.ArgumentParser(description="Telegram Skill Tool")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # Send Message
    send_parser = subparsers.add_parser("send", help="Send a message")
    send_parser.add_argument("--chat_id", required=True, help="Chat ID")
    send_parser.add_argument("--text", required=True, help="Message text")

    # Check Updates
    subparsers.add_parser("check-updates", help="Check for updates")

    args = parser.parse_args()

    if args.action == "send":
        asyncio.run(send_message(args.chat_id, args.text))
    elif args.action == "check-updates":
        asyncio.run(check_updates())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
