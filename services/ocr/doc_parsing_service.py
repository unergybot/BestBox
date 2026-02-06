import os
import logging
import tempfile
import io
from pathlib import Path
from typing import Optional, List
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("docling-service")

app = FastAPI(title="Docling Parsing Service")

# Configuration
OCR_SERVICE_URL = os.environ.get("OCR_SERVICE_URL", "http://ocr-service:8084")
OCR_MIN_TEXT_CHARS = int(os.environ.get("OCR_MIN_TEXT_CHARS", "50"))


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


def get_page_text_lengths(doc) -> dict:
    """Get the total text length extracted by Docling for each page."""
    from docling_core.types.doc import TextItem

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
    """Parse a document using Docling and delegate OCR to the GPU service."""
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        # Configure Docling: disable built-in OCR, enable page image generation
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.generate_page_images = True
        pipeline_options.images_scale = 2.0  # 2x for good OCR quality

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )

        # Save uploaded file
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {'.pdf', '.docx', '.pptx'}:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            logger.info(f"Parsing document: {file.filename}")

            # 1. Convert with Docling (OCR disabled, page images enabled)
            result = converter.convert(str(tmp_path))
            text = result.document.export_to_markdown()
            logger.info(f"Docling extracted {len(text)} chars of text")

            # 2. Find pages that need GPU OCR
            ocr_results = []
            pages_ocrd = 0

            if run_ocr and suffix == '.pdf':
                page_text_lengths = get_page_text_lengths(result.document)
                total_pages = len(result.document.pages)
                logger.info(f"Document has {total_pages} pages, checking text coverage")

                for page_no, page in result.document.pages.items():
                    chars_on_page = page_text_lengths.get(page_no, 0)

                    if chars_on_page < OCR_MIN_TEXT_CHARS:
                        logger.info(
                            f"Page {page_no}: only {chars_on_page} chars, "
                            f"delegating to GPU OCR at {OCR_SERVICE_URL}"
                        )
                        image_bytes = render_page_to_png(page)
                        if image_bytes:
                            ocr_text = await run_gpu_ocr_bytes(
                                image_bytes, f"page_{page_no}.png"
                            )
                            if ocr_text:
                                ocr_results.append({
                                    "image_index": page_no,
                                    "page": page_no,
                                    "text": ocr_text
                                })
                                pages_ocrd += 1
                        else:
                            logger.warning(f"Page {page_no}: no image available for OCR")
                    else:
                        logger.info(f"Page {page_no}: {chars_on_page} chars, skipping OCR")

                logger.info(f"GPU OCR completed: {pages_ocrd}/{total_pages} pages processed")

            # 3. Combine results
            combined_text = text
            if ocr_results:
                combined_text += "\n\n## OCR Extracted Text\n\n"
                for ocr_item in ocr_results:
                    combined_text += f"### Page {ocr_item['page']}\n\n"
                    combined_text += f"{ocr_item['text']}\n\n"

            metadata = {
                "source": file.filename,
                "file_type": suffix.lstrip("."),
                "domain": domain,
                "image_count": pages_ocrd,
                "ocr_count": len(ocr_results),
                "total_pages": len(result.document.pages) if hasattr(result.document, 'pages') else 0,
                "docling_text_length": len(text)
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
