"""
BestBox Reranker Service
Serves BGE-reranker-base for precision boosting in RAG pipeline
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import CrossEncoder
from typing import List
import time
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BestBox Reranker API",
    description="BGE-reranker-base for RAG precision boosting",
    version="1.0.0"
)

# Global model instance
model = None

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

@app.on_event("startup")
async def load_model():
    global model
    logger.info("Loading BGE-reranker-base model...")
    start = time.time()
    model = CrossEncoder("BAAI/bge-reranker-base")
    elapsed = time.time() - start
    logger.info(f"Model loaded in {elapsed:.2f}s")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok" if model is not None else "loading",
        model_loaded=model is not None,
        model_name="BAAI/bge-reranker-base"
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

    # Score pairs
    start = time.time()
    scores = model.predict(pairs)
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
        "model": "BAAI/bge-reranker-base",
        "endpoints": {
            "health": "/health",
            "rerank": "/rerank (POST)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082)
