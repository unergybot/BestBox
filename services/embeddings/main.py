"""
BestBox Embeddings Service
Serves BGE-M3 embeddings via FastAPI for RAG pipeline
"""
import os
# Force CPU-only to avoid CUDA OOM (RTX 3080 is full with vLLM)
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union
import time
import logging

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
async def load_model():
    global model
    logger.info("Loading BGE-M3 embedding model...")
    start = time.time()
    # Use CPU to avoid CUDA OOM (RTX 3080 is full with vLLM, Tesla P100 incompatible with PyTorch 2.10)
    device = "cpu"
    logger.info(f"Using device: {device}")
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    elapsed = time.time() - start
    logger.info(f"Model loaded in {elapsed:.2f}s on {device}")
    logger.info(f"Embedding dimensions: {model.get_sentence_embedding_dimension()}")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok" if model is not None else "loading",
        model_loaded=model is not None,
        model_name="BAAI/bge-m3"
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
        model="BAAI/bge-m3",
        inference_time_ms=round(elapsed_ms, 2)
    )

@app.get("/")
async def root():
    return {
        "service": "BestBox Embeddings API",
        "model": "BAAI/bge-m3",
        "endpoints": {
            "health": "/health",
            "embed": "/embed (POST)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081)
