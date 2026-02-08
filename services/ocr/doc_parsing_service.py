import os
import re
import logging
import tempfile
import io
from pathlib import Path
from typing import Optional, List
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("docling-service")

app = FastAPI(title="Docling Parsing Service")

OCR_SERVICE_URL = os.environ.get("OCR_SERVICE_URL", "http://ocr-service:8084")
GLM_OCR_URL = os.environ.get("GLM_OCR_URL", "http://glm-ocr-service:11434")
GPU_SCHEDULER_URL = os.environ.get("GPU_SCHEDULER_URL", "http://gpu-scheduler:8086")
OCR_MIN_TEXT_CHARS = int(os.environ.get("OCR_MIN_TEXT_CHARS", "50"))
GARBAGE_THRESHOLD = float(os.environ.get("GARBAGE_THRESHOLD", "0.30"))
ENABLE_QUALITY_GATE = os.environ.get("ENABLE_QUALITY_GATE", "true").lower() == "true"
ENABLE_GLM_OCR_FALLBACK = os.environ.get("ENABLE_GLM_OCR_FALLBACK", "true").lower() == "true"


class ParseResponse(BaseModel):
    """Document parsing response."""
    text: str
    raw_text: str
    image_count: int
    ocr_results: List[dict]
    metadata: dict
    success: bool = True
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "docling-cpu"}


async def run_gpu_ocr(image_path: Path) -> str:
    """Call the dedicated GPU OCR service for an image."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/png")}
                response = await client.post(f"{OCR_SERVICE_URL}/ocr", files=files)

                if response.status_code == 200:
                    result = response.json()
                    return result.get("text", "")
                else:
                    logger.error(f"GPU OCR failed with status {response.status_code}: {response.text}")
                    return ""
    except Exception as e:
        logger.error(f"Error calling GPU OCR service: {e}")
        return ""


async def run_gpu_ocr_bytes(image_bytes: bytes, filename: str) -> str:
    """Call the dedicated GPU OCR service with in-memory image bytes."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (filename, image_bytes, "image/png")}
            response = await client.post(f"{OCR_SERVICE_URL}/ocr", files=files)

            if response.status_code == 200:
                result = response.json()
                return result.get("text", "")
            else:
                logger.error(f"GPU OCR failed with status {response.status_code}: {response.text}")
                return ""
    except Exception as e:
        logger.error(f"Error calling GPU OCR service: {e}")
        return ""


def check_quality_issues(text: str) -> dict:
    """Check for quality issues in extracted text."""
    issues = {
        "empty_blocks": False,
        "high_garbage_ratio": False,
        "table_collapsed": False,
        "very_short": False,
        "garbage_ratio": 0.0
    }
    
    if not text or len(text.strip()) == 0:
        issues["empty_blocks"] = True
        return issues
    
    if len(text) < OCR_MIN_TEXT_CHARS:
        issues["very_short"] = True
    
    non_ascii_count = sum(1 for c in text if ord(c) > 127)
    total_chars = len(text)
    garbage_ratio = non_ascii_count / total_chars if total_chars > 0 else 0
    issues["garbage_ratio"] = garbage_ratio
    
    if garbage_ratio > GARBAGE_THRESHOLD:
        issues["high_garbage_ratio"] = True
    
    table_indicators = ['|', '───', '┌', '┐', '└', '┘', '├', '┤', '┬', '┴', '┼']
    has_table_markers = any(marker in text for marker in table_indicators)
    if has_table_markers and len(text) < 100:
        issues["table_collapsed"] = True
    
    return issues


async def run_glm_ocr_with_scheduling(image_bytes: bytes, filename: str, page_num: int) -> str:
    """Run GLM-OCR with GPU scheduling for quality fallback."""
    if not ENABLE_GLM_OCR_FALLBACK:
        return ""
    
    worker_id = f"docling-page-{page_num}"
    
    try:
        from services.ocr.glm_ocr_client import GLMOCRClient
        
        client = GLMOCRClient(
            base_url=GLM_OCR_URL,
            scheduler_url=GPU_SCHEDULER_URL
        )
        
        text = await client.extract_text_bytes(
            image_bytes=image_bytes,
            filename=filename,
            prompt="Extract all text from this document page. Preserve layout, tables, and formatting. Output as markdown.",
            worker_id=worker_id
        )
        
        await client.close()
        return text
        
    except Exception as e:
        logger.error(f"GLM-OCR fallback failed for page {page_num}: {e}")
        return ""


def get_page_text_lengths(doc) -> dict:
    from docling_core.types.doc.document import TextItem

    page_text = {}
    for item, _level in doc.iterate_items():
        if isinstance(item, TextItem) and item.prov:
            for prov in item.prov:
                page_no = prov.page_no
                text_len = len(item.text) if item.text else 0
                page_text[page_no] = page_text.get(page_no, 0) + text_len
    return page_text


def render_page_to_png(page) -> Optional[bytes]:
    """Render a Docling page image to PNG bytes."""
    if page.image and page.image.pil_image:
        buf = io.BytesIO()
        page.image.pil_image.save(buf, format="PNG")
        return buf.getvalue()
    return None


@app.post("/parse", response_model=ParseResponse)
async def parse_document(
    file: UploadFile = File(...),
    run_ocr: bool = True,
    domain: str = "mold"
):
    """Parse a document using Docling with quality gate and OCR-VL escalation."""
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.generate_page_images = True
        pipeline_options.images_scale = 2.0

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )

        filename = file.filename or "document.pdf"
        suffix = Path(filename).suffix.lower()
        if suffix not in {'.pdf', '.docx', '.pptx'}:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            logger.info(f"Parsing document: {file.filename}")

            result = converter.convert(str(tmp_path))
            text = result.document.export_to_markdown()
            logger.info(f"Docling extracted {len(text)} chars of text")

            ocr_results = []
            pages_ocrd = 0
            pages_escalated = 0

            if run_ocr and suffix == '.pdf':
                page_text_lengths = get_page_text_lengths(result.document)
                total_pages = len(result.document.pages)
                logger.info(f"Document has {total_pages} pages, checking text coverage")

                for page_no, page in result.document.pages.items():
                    chars_on_page = page_text_lengths.get(page_no, 0)
                    page_needs_ocr = chars_on_page < OCR_MIN_TEXT_CHARS
                    
                    image_bytes = render_page_to_png(page)
                    if not image_bytes:
                        logger.warning(f"Page {page_no}: no image available for OCR")
                        continue

                    ocr_text = ""
                    quality_failed = False
                    
                    if page_needs_ocr:
                        logger.info(
                            f"Page {page_no}: only {chars_on_page} chars, "
                            f"delegating to GPU OCR at {OCR_SERVICE_URL}"
                        )
                        ocr_text = await run_gpu_ocr_bytes(
                            image_bytes, f"page_{page_no}.png"
                        )
                        
                        if ENABLE_QUALITY_GATE and ocr_text:
                            quality = check_quality_issues(ocr_text)
                            if any([
                                quality["high_garbage_ratio"],
                                quality["table_collapsed"],
                                quality["empty_blocks"]
                            ]):
                                logger.warning(
                                    f"Page {page_no}: quality check failed "
                                    f"(garbage_ratio={quality['garbage_ratio']:.2f}), "
                                    f"escalating to GLM-OCR"
                                )
                                quality_failed = True
                    
                    if quality_failed or (ENABLE_QUALITY_GATE and page_needs_ocr and not ocr_text):
                        logger.info(f"Page {page_no}: escalating to GLM-OCR on RTX 3080")
                        glm_text = await run_glm_ocr_with_scheduling(
                            image_bytes, f"page_{page_no}.png", page_no
                        )
                        if glm_text:
                            ocr_text = glm_text
                            pages_escalated += 1
                            logger.info(f"Page {page_no}: GLM-OCR extracted {len(glm_text)} chars")
                    
                    if ocr_text:
                        ocr_results.append({
                            "image_index": page_no,
                            "page": page_no,
                            "text": ocr_text,
                            "source": "glm-ocr" if quality_failed or pages_escalated > 0 else "got-ocr"
                        })
                        pages_ocrd += 1
                    else:
                        logger.info(f"Page {page_no}: {chars_on_page} chars, skipping OCR")

                logger.info(
                    f"OCR complete: {pages_ocrd}/{total_pages} pages processed, "
                    f"{pages_escalated} escalated to GLM-OCR"
                )

            combined_text = text
            if ocr_results:
                combined_text += "\n\n## OCR Extracted Text\n\n"
                for ocr_item in ocr_results:
                    combined_text += f"### Page {ocr_item['page']} ({ocr_item['source']})\n\n"
                    combined_text += f"{ocr_item['text']}\n\n"

            metadata = {
                "source": file.filename,
                "file_type": suffix.lstrip("."),
                "domain": domain,
                "image_count": pages_ocrd,
                "ocr_count": len(ocr_results),
                "pages_escalated": pages_escalated,
                "total_pages": len(result.document.pages) if hasattr(result.document, 'pages') else 0,
                "docling_text_length": len(text),
                "quality_gate_enabled": ENABLE_QUALITY_GATE,
                "glm_ocr_fallback_enabled": ENABLE_GLM_OCR_FALLBACK
            }

            return ParseResponse(
                text=combined_text,
                raw_text=text,
                image_count=pages_ocrd,
                ocr_results=ocr_results,
                metadata=metadata
            )

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document parsing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("DOC_PORT", 8085))
    uvicorn.run(app, host="0.0.0.0", port=port)
