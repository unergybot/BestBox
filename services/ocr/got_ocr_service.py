"""GOT-OCR2.0 Service for Mold Knowledge Base.

FastAPI service providing OCR capabilities using stepfun-ai/GOT-OCR2_0 model.
Optimized for P100 GPU (16GB VRAM, CUDA 11.8).
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Configuration
MODEL_NAME = "stepfun-ai/GOT-OCR2_0"
MAX_IMAGE_SIZE = 2048  # Resize larger images to save VRAM


class OCRResponse(BaseModel):
    """OCR extraction response."""
    text: str
    model: str = MODEL_NAME
    success: bool = True
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model: str
    gpu: str
    vram_used_gb: float
    vram_total_gb: float


# Initialize FastAPI app
app = FastAPI(
    title="GOT-OCR2.0 Service",
    description="OCR service for mold manufacturing documents",
    version="1.0.0"
)

# Lazy load model to avoid loading on import
_model = None
_tokenizer = None


def get_model():
    """Lazy load model and tokenizer."""
    global _model, _tokenizer
    
    if _model is None:
        logger.info(f"Loading model: {MODEL_NAME}")
        from transformers import AutoModel, AutoTokenizer
        
        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, 
            trust_remote_code=True
        )
        _model = AutoModel.from_pretrained(
            MODEL_NAME,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            device_map='cuda',
            use_safetensors=True,
            torch_dtype=torch.float16  # Use FP16 for P100
        ).eval()
        
        logger.info(f"Model loaded on {torch.cuda.get_device_name(0)}")
    
    return _model, _tokenizer


def resize_image_if_needed(image_path: Path) -> Path:
    """Resize image if larger than MAX_IMAGE_SIZE to save VRAM."""
    from PIL import Image
    
    with Image.open(image_path) as img:
        if max(img.size) > MAX_IMAGE_SIZE:
            ratio = MAX_IMAGE_SIZE / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save resized image
            resized_path = image_path.with_suffix('.resized.png')
            img.save(resized_path)
            logger.info(f"Resized image from {img.size} to {new_size}")
            return resized_path
    
    return image_path


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint with GPU info."""
    try:
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        vram_used = torch.cuda.memory_allocated(0) / 1e9 if torch.cuda.is_available() else 0
        vram_total = torch.cuda.get_device_properties(0).total_memory / 1e9 if torch.cuda.is_available() else 0
        
        return HealthResponse(
            status="ok",
            model=MODEL_NAME,
            gpu=gpu_name,
            vram_used_gb=round(vram_used, 2),
            vram_total_gb=round(vram_total, 2)
        )
    except Exception as e:
        return HealthResponse(
            status="error",
            model=MODEL_NAME,
            gpu=str(e),
            vram_used_gb=0,
            vram_total_gb=0
        )


@app.post("/ocr", response_model=OCRResponse)
async def ocr(file: UploadFile = File(...), ocr_type: str = "ocr"):
    """
    Extract text from image using GOT-OCR2.0.
    
    Args:
        file: Image file (PNG, JPG, etc.)
        ocr_type: OCR mode - 'ocr' (plain text) or 'format' (with formatting)
    
    Returns:
        OCRResponse with extracted text
    """
    try:
        model, tokenizer = get_model()
        
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
        
        try:
            # Resize if needed
            image_path = resize_image_if_needed(tmp_path)
            
            # Run OCR
            logger.info(f"Running OCR on {file.filename} (type={ocr_type})")
            result = model.chat(tokenizer, str(image_path), ocr_type=ocr_type)
            
            return OCRResponse(text=result)
            
        finally:
            # Cleanup temp files
            tmp_path.unlink(missing_ok=True)
            resized_path = tmp_path.with_suffix('.resized.png')
            if resized_path.exists():
                resized_path.unlink()
                
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ocr/batch", response_model=list[OCRResponse])
async def ocr_batch(files: list[UploadFile] = File(...), ocr_type: str = "ocr"):
    """
    Batch OCR for multiple images.
    
    Args:
        files: List of image files
        ocr_type: OCR mode
    
    Returns:
        List of OCRResponse for each image
    """
    results = []
    for file in files:
        try:
            result = await ocr(file, ocr_type)
            results.append(result)
        except HTTPException as e:
            results.append(OCRResponse(
                text="",
                success=False,
                error=str(e.detail)
            ))
    return results


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("OCR_PORT", 8084))
    logger.info(f"Starting GOT-OCR2.0 service on port {port}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
