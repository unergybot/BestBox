from .base import ClawdBotSkillTool
import logging
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_SDK_AVAILABLE = True
except ImportError:
    SLACK_SDK_AVAILABLE = False

class SlackTool(ClawdBotSkillTool):
    """
    Slack skill adapter using slack_sdk.
    """
    def __init__(self):
        super().__init__("slack")
        self.client = None
        if SLACK_SDK_AVAILABLE:
            token = os.environ.get("SLACK_BOT_TOKEN")
            if token:
                self.client = WebClient(token=token)
            else:
                logger.warning("SLACK_BOT_TOKEN not found in environment variables.")
        else:
            logger.warning("slack_sdk not installed. SlackTool will not function.")

    def _check_client(self) -> Dict[str, Any]:
        """
        Check if client is initialized.
        """
        if not SLACK_SDK_AVAILABLE:
            return {"ok": False, "error": "slack_sdk library not installed"}
        if not self.client:
            return {"ok": False, "error": "SLACK_BOT_TOKEN not set"}
        return {"ok": True}

    def chat_postMessage(self, channel: str, text: str) -> Dict[str, Any]:
        """
        Send a message to a channel.
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        try:
            response = self.client.chat_postMessage(channel=channel, text=text)
            return {"ok": True, "ts": response["ts"], "channel": response["channel"]}
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return {"ok": False, "error": e.response['error']}

    def conversations_history(self, channel: str, limit: int = 10) -> Dict[str, Any]:
        """
        Get message history from a channel.
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        try:
            response = self.client.conversations_history(channel=channel, limit=limit)
            messages = response.get("messages", [])
            return {"ok": True, "messages": messages}
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return {"ok": False, "error": e.response['error']}

    def users_info(self, user: str) -> Dict[str, Any]:
        """
        Get information about a user.
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        try:
            response = self.client.users_info(user=user)
            return {"ok": True, "user": response["user"]}
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return {"ok": False, "error": e.response['error']}

    def reactions_add(self, channel: str, timestamp: str, name: str) -> Dict[str, Any]:
        """
        Add a reaction to a message.
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        try:
            self.client.reactions_add(channel=channel, timestamp=timestamp, name=name)
            return {"ok": True}
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return {"ok": False, "error": e.response['error']}
