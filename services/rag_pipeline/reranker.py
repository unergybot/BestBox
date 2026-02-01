"""
BestBox Reranker Service
Serves BGE-reranker-base for precision boosting in RAG pipeline
"""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import CrossEncoder
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL_NAME = "BAAI/bge-reranker-base"

# Global model instance
model = None

# Thread pool for CPU-bound operations
executor = ThreadPoolExecutor(max_workers=4)


def _cuda_available() -> bool:
    """Return True if CUDA is available via PyTorch."""
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def _resolve_device() -> str:
    """Resolve device string from environment with safe fallbacks."""
    requested = os.environ.get("RERANKER_DEVICE", "auto").strip().lower()
    if requested in {"", "auto"}:
        return "cuda" if _cuda_available() else "cpu"
    if requested.startswith("cuda"):
        if _cuda_available():
            return requested
        logger.warning("CUDA requested for reranker, but CUDA is unavailable. Falling back to CPU.")
        return "cpu"
    return requested

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global model
    model_name = os.environ.get("RERANKER_MODEL_NAME", DEFAULT_MODEL_NAME)
    device = _resolve_device()
    logger.info(f"Loading {model_name} model...")
    logger.info(f"Device: {device}")
    start = time.time()
    try:
        model = CrossEncoder(model_name, device=device)
        elapsed = time.time() - start
        logger.info(f"Model loaded in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        model = None

    yield

    # Shutdown (cleanup if needed)
    logger.info("Shutting down reranker service")

app = FastAPI(
    title="BestBox Reranker API",
    description="BGE-reranker for RAG pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RerankRequest(BaseModel):
    query: str
    passages: List[str]

class RerankResponse(BaseModel):
    scores: List[float]
    ranked_indices: List[int]
    inference_time_ms: float

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok" if model is not None else "loading",
        model_loaded=model is not None,
        model_name=os.environ.get("RERANKER_MODEL_NAME", DEFAULT_MODEL_NAME)
    )

@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # Handle empty passages
    if not request.passages:
        return RerankResponse(
            scores=[],
            ranked_indices=[],
            inference_time_ms=0.0
        )

    # Create query-passage pairs
    pairs = [[request.query, passage] for passage in request.passages]

    # Score pairs using executor to avoid blocking event loop
    start = time.time()
    loop = asyncio.get_event_loop()
    scores = await loop.run_in_executor(executor, model.predict, pairs)
    elapsed_ms = (time.time() - start) * 1000

    # Convert numpy array to list if needed
    if isinstance(scores, np.ndarray):
        scores = scores.tolist()

    # Get ranked indices (descending order - best first)
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    return RerankResponse(
        scores=scores,
        ranked_indices=ranked_indices,
        inference_time_ms=round(elapsed_ms, 2)
    )

@app.get("/")
async def root():
    return {
        "service": "BestBox Reranker API",
        "model": os.environ.get("RERANKER_MODEL_NAME", DEFAULT_MODEL_NAME),
        "endpoints": {
            "health": "/health",
            "rerank": "/rerank (POST)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
