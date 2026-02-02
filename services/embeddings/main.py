"""
BestBox Embeddings Service
Serves BGE-M3 embeddings via FastAPI for RAG pipeline
"""
import logging
import os
import time
from typing import List, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BestBox Embeddings API",
    description="BGE-M3 embeddings for RAG pipeline",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model instance
model = None

DEFAULT_MODEL_NAME = "BAAI/bge-m3"


def _cuda_available() -> bool:
    """Return True if CUDA is available via PyTorch."""
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def _resolve_device() -> str:
    """Resolve device string from environment with safe fallbacks."""
    requested = os.environ.get("EMBEDDINGS_DEVICE", "auto").strip().lower()
    if requested in {"", "auto"}:
        return "cuda" if _cuda_available() else "cpu"
    if requested.startswith("cuda"):
        if _cuda_available():
            return requested
        logger.warning("CUDA requested for embeddings, but CUDA is unavailable. Falling back to CPU.")
        return "cpu"
    return requested

class EmbedRequest(BaseModel):
    inputs: Union[str, List[str]]
    normalize: bool = True

class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    dimensions: int
    model: str
    inference_time_ms: float

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str

@app.on_event("startup")
async def load_model() -> None:
    global model
    model_name = os.environ.get("EMBEDDINGS_MODEL_NAME", DEFAULT_MODEL_NAME)
    device = _resolve_device()
    dtype_env = os.environ.get("EMBEDDINGS_DTYPE", "auto").strip().lower()
    logger.info("Loading embedding model...")
    logger.info(f"Model: {model_name}")
    logger.info(f"Device: {device}")
    start = time.time()

    model_kwargs = None
    if device.startswith("cuda"):
        # Default to fp16 on CUDA to reduce VRAM usage and avoid OOM.
        # SentenceTransformer forwards model_kwargs to transformers AutoModel.
        try:
            import torch

            if dtype_env in {"", "auto"}:
                torch_dtype = torch.float16
            elif dtype_env in {"fp16", "float16"}:
                torch_dtype = torch.float16
            elif dtype_env in {"bf16", "bfloat16"}:
                torch_dtype = torch.bfloat16
            elif dtype_env in {"fp32", "float32"}:
                torch_dtype = torch.float32
            else:
                logger.warning("Unknown EMBEDDINGS_DTYPE=%s; falling back to fp16", dtype_env)
                torch_dtype = torch.float16
            model_kwargs = {"torch_dtype": torch_dtype}
        except Exception as e:
            logger.warning("Failed to configure embeddings dtype; proceeding with defaults: %s", e)

    try:
        if model_kwargs is not None:
            model = SentenceTransformer(model_name, device=device, model_kwargs=model_kwargs)
        else:
            model = SentenceTransformer(model_name, device=device)
    except TypeError:
        # Backward compatibility with older sentence-transformers versions.
        model = SentenceTransformer(model_name, device=device)
    elapsed = time.time() - start
    logger.info(f"Model loaded in {elapsed:.2f}s")
    logger.info(f"Embedding dimensions: {model.get_sentence_embedding_dimension()}")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok" if model is not None else "loading",
        model_loaded=model is not None,
        model_name=os.environ.get("EMBEDDINGS_MODEL_NAME", DEFAULT_MODEL_NAME)
    )

@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    
    # Handle single string or list of strings
    texts = request.inputs if isinstance(request.inputs, list) else [request.inputs]
    
    start = time.time()
    embeddings = model.encode(
        texts, 
        normalize_embeddings=request.normalize,
        show_progress_bar=False
    )
    elapsed_ms = (time.time() - start) * 1000
    
    return EmbedResponse(
        embeddings=embeddings.tolist(),
        dimensions=model.get_sentence_embedding_dimension(),
        model=os.environ.get("EMBEDDINGS_MODEL_NAME", DEFAULT_MODEL_NAME),
        inference_time_ms=round(elapsed_ms, 2)
    )

@app.get("/")
async def root():
    return {
        "service": "BestBox Embeddings API",
        "model": os.environ.get("EMBEDDINGS_MODEL_NAME", DEFAULT_MODEL_NAME),
        "endpoints": {
            "health": "/health",
            "embed": "/embed (POST)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081)
