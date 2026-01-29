---
name: telegram
description: "Interact with Telegram to send messages and check updates."
metadata:
  clawdbot:
    emoji: "✈️"
    requires:
      python_packages: ["python-telegram-bot"]
      env_vars: ["TELEGRAM_BOT_TOKEN"]
---

# Telegram Skill

Use the Python `telegram_tool.py` script to interact with Telegram.

## Send Message

Send a message to a chat ID:
```bash
python3 skills/telegram/telegram_tool.py send --chat_id "123456789" --text "Hello from BestBox!"
```

## Check Updates

Check for recent updates (messages) to find your chat ID:
```bash
python3 skills/telegram/telegram_tool.py check-updates
```
