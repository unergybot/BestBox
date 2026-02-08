"""
GLM-OCR Vision-Language Service with Transformers
Uses bleeding-edge transformers from git for GLM-OCR support
"""
import os
import io
import base64
from typing import Optional, List
import torch
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import fitz  # PyMuPDF

# Configuration
MODEL_NAME = os.getenv("MODEL_NAME", "zai-org/GLM-OCR")
DEVICE = os.getenv("DEVICE", "cuda:0")
PORT = int(os.getenv("GLM_OCR_PORT", "11436"))

app = FastAPI(title="GLM-OCR Service", version="1.0.0")

processor = None
model = None


class OCRRequest(BaseModel):
    image: str  # Base64
    prompt: Optional[str] = "Text Recognition:"
    max_new_tokens: int = 8192


class OCRResponse(BaseModel):
    text: str
    processing_time: float


@app.on_event("startup")
async def load_model():
    global processor, model
    
    print(f"Loading GLM-OCR: {MODEL_NAME} on {DEVICE}")
    
    processor = AutoProcessor.from_pretrained(MODEL_NAME)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_NAME,
        torch_dtype="auto",
        device_map=DEVICE
    )
    
    print(f"✅ Model ready on {DEVICE}")


@app.get("/health")
async def health():
    if model is None:
        raise HTTPException(503, "Model not loaded")
    return {"status": "healthy", "model": MODEL_NAME, "device": DEVICE}


@app.post("/v1/ocr", response_model=OCRResponse)
async def ocr(request: OCRRequest):
    import time
    start = time.time()
    
    try:
        # Decode image
        img_bytes = base64.b64decode(request.image)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        # Prepare messages in chat format
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": request.prompt}
            ]
        }]
        
        # Apply chat template
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)
        
        # Remove token_type_ids if present
        inputs.pop("token_type_ids", None)
        
        # Generate
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=request.max_new_tokens
            )
        
        # Decode
        output_text = processor.decode(
            generated_ids[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        
        return OCRResponse(
            text=output_text,
            processing_time=time.time() - start
        )
        
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {e}")


@app.post("/v1/ocr/pdf")
async def ocr_pdf(file: UploadFile = File(...), page: Optional[int] = None):
    import time
    start = time.time()
    
    try:
        pdf_bytes = await file.read()
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        results = []
        pages = [page - 1] if page else range(len(pdf_doc))
        
        for page_num in pages:
            if page_num >= len(pdf_doc):
                continue
                
            # Render to image
            pix = pdf_doc[page_num].get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            
            # Process
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": "Text Recognition:"}
                ]
            }]
            
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt"
            ).to(model.device)
            
            inputs.pop("token_type_ids", None)
            
            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_new_tokens=8192)
            
            text = processor.decode(
                generated_ids[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )
            
            results.append({"page": page_num + 1, "text": text})
        
        pdf_doc.close()
        
        return {
            "pages": results,
            "total_pages": len(pdf_doc),
            "processing_time": time.time() - start
        }
        
    except Exception as e:
        raise HTTPException(500, f"PDF processing failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
