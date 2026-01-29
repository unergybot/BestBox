
import os
import logging
import asyncio
import aiohttp
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("telegram_gateway")

# Load environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AGENT_API_URL = os.environ.get("AGENT_API_URL", "http://localhost:8000/v1/chat/completions")

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is not set")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    username = update.effective_user.username or "unknown"

    logger.info(f"Received message from {username} ({user_id}) in {chat_id}: {text}")

    # Indicate typing status
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Call Agent API
        async with aiohttp.ClientSession() as session:
            payload = {
                "messages": [
                    {"role": "user", "content": text}
                ],
                "model": "bestbox-agent",
                "stream": False,
                # Use chat_id as session_id to maintain context per chat
                "thread_id": f"telegram-{chat_id}"
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-user-id": f"telegram:{user_id}"
            }

            async with session.post(AGENT_API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response_text = data["choices"][0]["message"]["content"]
                    
                    # Send response back to Telegram
                    await context.bot.send_message(chat_id=chat_id, text=response_text)
                else:
                    error_text = await resp.text()
                    logger.error(f"Agent API error: {resp.status} - {error_text}")
                    await context.bot.send_message(chat_id=chat_id, text=f"⚠️ BestBox API Error: {resp.status}")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Internal Error: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm BestBox Agent. How can I help you?")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Cannot start Telegram Gateway without TELEGRAM_BOT_TOKEN")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(message_handler)
    
    logger.info("⚡️ BestBox Telegram Gateway is polling!")
    application.run_polling()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Check configuration and exit")
    args = parser.parse_args()

    if args.dry_run:
        if TELEGRAM_BOT_TOKEN:
            try:
                import telegram
                print(f"Configuration OK: Token present. python-telegram-bot version: {telegram.__version__}")
            except ImportError:
                print("Configuration Error: python-telegram-bot not installed")
                exit(1)
        else:
            print("Configuration Error: TELEGRAM_BOT_TOKEN missing.")
            exit(1)
    else:
        main()
