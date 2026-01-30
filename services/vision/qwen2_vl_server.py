#!/usr/bin/env python3
"""
Qwen2-VL-7B Vision-Language Model Service

Provides image understanding for troubleshooting equipment photos.
Runs on AMD ROCm GPU alongside other BestBox services.

Usage:
    uvicorn services.vision.qwen2_vl_server:app --host 0.0.0.0 --port 8083
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import torch
import io
import json
from typing import Optional
from contextlib import asynccontextmanager
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model holder
vl_service = None


class Qwen2VLService:
    """Qwen2.5-VL-3B model service for equipment image analysis"""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-VL-3B-Instruct"):
        logger.info(f"Initializing Qwen2-VL service: {model_name}")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

        if not torch.cuda.is_available():
            logger.warning("CUDA not available! Running on CPU (very slow)")

        try:
            # Import here to allow graceful degradation
            # Use AutoModelForVision2Seq for better compatibility
            from transformers import AutoModelForVision2Seq, AutoProcessor

            # Load Qwen2.5-VL model (smaller, faster)
            logger.info("Loading Qwen2.5-VL model (this may take a few minutes)...")
            self.model = AutoModelForVision2Seq.from_pretrained(
                model_name,
                dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                trust_remote_code=True,
                attn_implementation="eager"  # Avoid flash attention issues on ROCm
            )

            self.processor = AutoProcessor.from_pretrained(
                model_name,
                trust_remote_code=True
            )

            logger.info(f"✅ {model_name} model loaded successfully")
            logger.info(f"   Model memory: ~{torch.cuda.memory_allocated() / 1024**3:.2f}GB")

        except Exception as e:
            logger.error(f"Failed to load VL model: {e}")
            raise

    def analyze_equipment_image(self, image: Image.Image, language: str = "zh") -> dict:
        """
        Analyze equipment/defect photo for troubleshooting documentation.

        Args:
            image: PIL Image to analyze
            language: Output language ('zh' for Chinese, 'en' for English)

        Returns:
            dict with defect_type, equipment_part, visual_annotations,
            text_in_image, detailed_description
        """

        # Prepare prompt based on language
        if language == "zh":
            prompt = """请仔细分析这张设备或产品照片，这是用于故障排除文档的技术图像。

请识别并描述：
1. **缺陷类型**：如产品披锋、拉白、火花纹残留、划痕、污染、变形等
2. **涉及部件**：模具表面、产品边缘、骨位、浇口等具体位置
3. **可见标注**：照片中的红圈、箭头、文字标记等
4. **图像文字**：提取照片中的所有文字内容（包括标注、测量值等）
5. **详细描述**：完整的技术描述，包括缺陷位置、严重程度、特征

请以JSON格式返回：
```json
{
  "defect_type": "缺陷类型（如'产品披锋'、'模具拖铁粉'等）",
  "equipment_part": "部件位置（如'模具表面'、'产品底部边缘'等）",
  "visual_annotations": "可见的标注描述（如'红色圆圈标记缺陷位置'）",
  "text_in_image": "提取的所有文字",
  "detailed_description": "完整的技术描述（2-3句话）"
}
```

如果无法识别某些信息，对应字段返回空字符串。"""
        else:
            prompt = """Analyze this equipment or product photo for troubleshooting documentation.

Identify and describe:
1. **Defect type**: flash, whitening, spark marks, scratches, contamination, deformation, etc.
2. **Equipment part**: mold surface, product edge, rib, gate, specific location
3. **Visual annotations**: red circles, arrows, text markers visible in photo
4. **Text in image**: Extract all text (annotations, measurements, etc.)
5. **Detailed description**: Complete technical description including location, severity, characteristics

Return in JSON format:
```json
{
  "defect_type": "type of defect",
  "equipment_part": "part location",
  "visual_annotations": "description of visible markings",
  "text_in_image": "extracted text",
  "detailed_description": "complete technical description (2-3 sentences)"
}
```

Return empty strings for fields that cannot be identified."""

        try:
            # Prepare messages for chat template
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]

            # Apply chat template
            text = self.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            # Prepare inputs
            inputs = self.processor(
                text=[text],
                images=[image],
                return_tensors="pt",
                padding=True
            ).to(self.device)

            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.3,  # Lower temperature for more consistent outputs
                    do_sample=True,
                    top_p=0.9
                )

            # Decode response
            generated_text = self.processor.batch_decode(
                outputs,
                skip_special_tokens=True
            )[0]

            # Extract JSON from response
            # The response contains the full conversation, extract just the assistant's response
            if "assistant" in generated_text:
                assistant_response = generated_text.split("assistant")[-1].strip()
            else:
                assistant_response = generated_text

            # Try to parse JSON
            try:
                # Find JSON block
                json_start = assistant_response.find('{')
                json_end = assistant_response.rfind('}') + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = assistant_response[json_start:json_end]
                    result = json.loads(json_str)
                else:
                    # Fallback: create structured output from text
                    result = {
                        "defect_type": "",
                        "equipment_part": "",
                        "visual_annotations": "",
                        "text_in_image": "",
                        "detailed_description": assistant_response
                    }
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                result = {
                    "defect_type": "",
                    "equipment_part": "",
                    "visual_annotations": "",
                    "text_in_image": "",
                    "detailed_description": assistant_response
                }

            return result

        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize model on startup"""
    global vl_service

    logger.info("Starting Qwen-VL service...")

    try:
        vl_service = Qwen2VLService()
        logger.info("✅ VL service ready")
    except Exception as e:
        logger.error(f"❌ Failed to initialize VL service: {e}")
        raise

    yield

    logger.info("Shutting down VL service...")


# Create FastAPI app
app = FastAPI(
    title="Qwen2.5-VL Image Analysis Service",
    description="Vision-Language model for equipment troubleshooting image analysis (Qwen2.5-VL-3B-Instruct)",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if vl_service is None:
        raise HTTPException(status_code=503, detail="VL service not initialized")

    return {
        "status": "healthy",
        "model": "Qwen2.5-VL-3B-Instruct",
        "device": vl_service.device,
        "gpu_available": torch.cuda.is_available(),
        "gpu_memory_allocated": f"{torch.cuda.memory_allocated() / 1024**3:.2f}GB" if torch.cuda.is_available() else "N/A"
    }


@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    language: str = "zh"
):
    """
    Analyze equipment/defect image for troubleshooting documentation.

    Args:
        file: Image file (JPEG, PNG)
        language: Output language ('zh' or 'en')

    Returns:
        JSON with defect analysis
    """
    if vl_service is None:
        raise HTTPException(status_code=503, detail="VL service not initialized")

    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        # Read and open image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Analyze image
        logger.info(f"Analyzing image: {file.filename} ({image.size})")
        result = vl_service.analyze_equipment_image(image, language=language)

        # Add metadata
        result['image_filename'] = file.filename
        result['image_size'] = f"{image.size[0]}x{image.size[1]}"

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "Qwen2-VL Image Analysis",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze-image (POST)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)
