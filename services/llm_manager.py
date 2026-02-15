"""Singleton LLM manager with config-aware client caching."""

import hashlib
import json
import logging
import threading
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class LLMManager:
    """Thread-safe singleton manager for cached ChatOpenAI clients."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.config_service = None
        self.current_client: Optional[ChatOpenAI] = None
        self.current_config_hash: Optional[str] = None
        self.client_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "LLMManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LLMManager()
        return cls._instance

    def get_client(self) -> ChatOpenAI:
        """Return cached client, refreshing when active config hash changes."""
        with self.client_lock:
            if self.config_service is None:
                self.config_service = get_llm_config_service()

            config = self.config_service.get_active_config()
            config_hash = self._hash_config(config)

            if config_hash != self.current_config_hash or self.current_client is None:
                logger.info(
                    "LLM config changed to %s/%s, refreshing client",
                    config.get("provider"),
                    config.get("model"),
                )
                self.current_client = self._create_client(config)
                self.current_config_hash = config_hash

            return self.current_client

    def force_refresh(self) -> None:
        """Invalidate current hash so next get_client refreshes client."""
        with self.client_lock:
            self.current_config_hash = None
            logger.info("LLM client cache invalidated")

    def _hash_config(self, config: Dict[str, Any]) -> str:
        payload = json.dumps(
            {
                "provider": config.get("provider"),
                "base_url": config.get("base_url"),
                "model": config.get("model"),
                "api_key": config.get("api_key") or "",
                "parameters": config.get("parameters") or {},
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _create_client(self, config: Dict[str, Any]) -> ChatOpenAI:
        try:
            parameters = config.get("parameters") or {}
            return ChatOpenAI(
                base_url=config["base_url"],
                api_key=config.get("api_key") or "sk-no-key-required",
                model=config["model"],
                temperature=parameters.get("temperature", 0.7),
                max_tokens=parameters.get("max_tokens", 4096),
                streaming=parameters.get("streaming", True),
                max_retries=parameters.get("max_retries", 2),
            )
        except Exception as exc:
            logger.error("Failed to create LLM client: %s", exc)
            logger.info("Falling back to local vLLM")
            return ChatOpenAI(
                base_url="http://localhost:8001/v1",
                api_key="sk-no-key-required",
                model="qwen3-30b",
                temperature=0.7,
                max_tokens=4096,
                streaming=True,
                max_retries=2,
            )


def get_llm_config_service():
    """Factory for LLMConfigService used by LLMManager."""
    from services.llm_config_service import LLMConfigService

    return LLMConfigService()
