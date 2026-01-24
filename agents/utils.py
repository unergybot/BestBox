from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
import os
import httpx

# Configuration for local services
LLM_BASE_URL = "http://127.0.0.1:8080/v1"
EMBEDDINGS_BASE_URL = "http://127.0.0.1:8081/v1" # OpenAI compatible endpoint if supported, otherwise we might need custom class

def get_llm(temperature: float = 0.7):
    """
    Get the configured ChatOpenAI instance connected to local llama-server.

    Note: The startup script unsets proxy environment variables to ensure local
    services can communicate directly without going through proxies.
    """
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        api_key="sk-no-key-required",  # Local server doesn't need real API key
        model="qwen2.5-14b",
        temperature=temperature,
        streaming=True
    )

class LocalBGEEmbeddings(OpenAIEmbeddings):
    """
    Custom wrapper for our local BGE-M3 service if needed.
    Since our FastAPI service exposes /embed, we might need a custom class if we strictly use that path.
    However, usually it is easier to just make the service OpenAI compatible or use a generic HTTP class.
    
    For now, let's assume we use a simple wrapper that calls our /embed endpoint.
    """
    def __init__(self, base_url: str = "http://127.0.0.1:8081"):
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
    def __init__(self, base_url: str = "http://127.0.0.1:8081"):
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
    return BGE3Embeddings()
