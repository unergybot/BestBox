from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
import os
import httpx
import logging

logger = logging.getLogger(__name__)

# Configuration for local services - use environment variables with defaults
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8001/v1")
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

def get_llm(temperature: float = 0.7, max_tokens: int = 4096):
    """
    Get the configured ChatOpenAI instance connected to local llama-server.

    Note: The startup script unsets proxy environment variables to ensure local
    services can communicate directly without going through proxies.

    Environment variables:
    - LLM_BASE_URL: URL of the LLM server (default: http://127.0.0.1:8001/v1)
    - LLM_MAX_TOKENS: Maximum tokens for response (default: 4096)
    """
    response_max_tokens = int(os.environ.get("LLM_MAX_TOKENS", str(max_tokens)))
    logger.info(f"Creating LLM client with base_url={LLM_BASE_URL}, max_tokens={response_max_tokens}")
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        api_key="sk-no-key-required",  # Local server doesn't need real API key
        model=os.environ.get("LLM_MODEL", "qwen3-30b"),
        temperature=temperature,
        streaming=True,
        max_retries=2,  # Retry on transient failures
        max_tokens=response_max_tokens,  # Ensure response isn't truncated
    )

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
