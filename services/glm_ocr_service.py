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


# Global Model Initialization
print(f"Loading GLM-OCR: {MODEL_NAME} on {DEVICE}")
processor = AutoProcessor.from_pretrained(MODEL_NAME, trust_remote_code=True)
model = AutoModelForImageTextToText.from_pretrained(
    MODEL_NAME,
    torch_dtype="auto",
    device_map=DEVICE,
    trust_remote_code=True
)
print(f"✅ Model ready on {DEVICE}")


@app.get("/health")
async def health():
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


@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    """Ollama/OpenAI compatible endpoint for GLM-SDK."""
    import time
    start = time.time()
    
    try:
        messages = request.get("messages", [])
        last_msg = messages[-1] if messages else {}
        prompt = "Text Recognition:"
        image = None
        
        # 1. Try to find prompt
        content = last_msg.get("content", "")
        if isinstance(content, str):
            prompt = content
        elif isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    prompt = item.get("text", prompt)

        # 2. Try to find image in standard locations
        # OpenAI style
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "image_url":
                    url = item.get("image_url", {}).get("url", "")
                    if "," in url:
                        image_data = url.split(",")[1]
                        image = Image.open(io.BytesIO(base64.b64decode(image_data))).convert("RGB")
                    elif len(url) > 1000: # Direct base64
                        image = Image.open(io.BytesIO(base64.b64decode(url))).convert("RGB")

        # Ollama style
        if image is None:
            ollama_images = last_msg.get("images", []) or request.get("images", []) or []
            if ollama_images:
                img_data = ollama_images[0]
                if "," in img_data: img_data = img_data.split(",")[1]
                image = Image.open(io.BytesIO(base64.b64decode(img_data))).convert("RGB")

        # 3. Recursive search (Deep dive)
        if image is None:
            def find_base64_recursively(obj):
                if isinstance(obj, str) and len(obj) > 1000:
                    try:
                        # Try to decode and open as image
                        data = obj.split(",")[1] if "," in obj else obj
                        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
                    except: return None
                elif isinstance(obj, dict):
                    for v in obj.values():
                        res = find_base64_recursively(v)
                        if res: return res
                elif isinstance(obj, list):
                    for v in obj:
                        res = find_base64_recursively(v)
                        if res: return res
                return None
            
            image = find_base64_recursively(request)

        if image is None:
            # Health check test request - return success for connection validation
            print(f"INFO: Health check request (no image). Keys: {list(request.keys())}")
            return {
                "choices": [{
                    "message": {"role": "assistant", "content": "Service is healthy"},
                    "finish_reason": "stop",
                    "index": 0
                }],
                "usage": {"total_tokens": 0}
            }
            
        print(f"Processing image for prompt: {prompt[:50]}...")
            
        # Prepare for Transformers
        inputs = processor.apply_chat_template(
            [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}],
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)
        
        inputs.pop("token_type_ids", None)
        
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=request.get("max_tokens", 8192)
            )
            
        output_text = processor.decode(
            generated_ids[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        
        duration = time.time() - start
        print(f"COMPLETED chat_completions in {duration:.2f}s")
        
        return {
            "choices": [{"message": {"role": "assistant", "content": output_text}, "finish_reason": "stop", "index": 0}],
            "usage": {"total_tokens": generated_ids.shape[1]}
        }
        
    except Exception as e:
        import traceback
        print(f"Error in chat_completions: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Chat completion failed: {e}")


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
