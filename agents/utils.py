from langchain_openai import OpenAIEmbeddings
import os
import httpx
import logging

logger = logging.getLogger(__name__)

# Configuration for local services - use environment variables with defaults
EMBEDDINGS_BASE_URL = os.environ.get("EMBEDDINGS_BASE_URL", "http://127.0.0.1:8004/v1")

SPEECH_FORMAT_INSTRUCTION = """
RESPONSE FORMAT:
You MUST format your response in two parts:
1. A short, conversational summary for speech synthesis (1-2 sentences), enclosed in [SPEECH] tags.
2. The full detailed response for the chat display.

Example:
[SPEECH]The Q4 revenue was 15 million dollars, which is a 20% increase.[/SPEECH]
Based on the financial reports, the Q4 revenue hit $15M... (rest of detailed answer)
"""

def get_llm(temperature: float = None, max_tokens: int = None):
    """Get LLM client from LLMManager using active runtime configuration."""
    from services.llm_manager import LLMManager

    client = LLMManager.get_instance().get_client()

    if temperature is not None or max_tokens is not None:
        overrides = {}
        if temperature is not None:
            overrides["temperature"] = temperature
        if max_tokens is not None:
            overrides["max_tokens"] = max_tokens
        if overrides:
            client = client.bind(**overrides)

    return client

class LocalBGEEmbeddings(OpenAIEmbeddings):
    """
    Custom wrapper for our local BGE-M3 service if needed.
    Since our FastAPI service exposes /embed, we might need a custom class if we strictly use that path.
    However, usually it is easier to just make the service OpenAI compatible or use a generic HTTP class.
    
    For now, let's assume we use a simple wrapper that calls our /embed endpoint.
    """
    def __init__(self, base_url: str = "http://127.0.0.1:8004"):
        super().__init__(
            base_url=base_url,
            api_key=None,
            model="bge-m3"
        )
        # Note: Our simple FastAPI in main.py exposes /embed, not /v1/embeddings.
        # We might need to adjust the service or use a custom function here.
        # Let's define a clean custom embedding class to call our specific endpoint.

import requests
from typing import List
from langchain_core.embeddings import Embeddings

class BGE3Embeddings(Embeddings):
    def __init__(self, base_url: str = "http://127.0.0.1:8004"):
        self.base_url = base_url

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = requests.post(
            f"{self.base_url}/embed",
            json={"inputs": texts, "normalize": True}
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    def embed_query(self, text: str) -> List[float]:
        response = requests.post(
            f"{self.base_url}/embed",
            json={"inputs": text, "normalize": True}
        )
        response.raise_for_status()
        data = response.json()
        # Our API returns list of embeddings, so take the first one
        return data["embeddings"][0]

def get_embeddings():
    base_url = os.environ.get("EMBEDDINGS_URL", "http://127.0.0.1:8004")
    return BGE3Embeddings(base_url=base_url)
