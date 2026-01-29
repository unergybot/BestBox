---
name: slack
description: "Interact with Slack to send messages, read history, and list channels."
metadata:
  clawdbot:
    emoji: "💬"
    requires:
      python_packages: ["slack_sdk"]
      env_vars: ["SLACK_BOT_TOKEN"]
---

# Slack Skill

Use the Python `slack_tool.py` script to interact with Slack.

## Send Message

Send a message to a channel:
```bash
python3 skills/slack/slack_tool.py send --channel "#general" --text "Hello from BestBox!"
```

## List Channels

List available channels:
```bash
python3 skills/slack/slack_tool.py list-channels --limit 10
```

## Read History

Read recent messages from a channel:
```bash
python3 skills/slack/slack_tool.py history --channel "#general"
```
