"""Tests for image extraction from Docling results."""

import base64
import io
from pathlib import Path
from unittest.mock import patch

import pytest

# Create a minimal 1x1 red PNG for testing
def _make_test_png_b64() -> str:
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (1, 1), (255, 0, 0))
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_extract_and_save_images_decodes_and_saves(tmp_path):
    """Should decode base64 images from Docling result and save as JPEG."""
    from services.admin_endpoints import _extract_and_save_images

    b64 = _make_test_png_b64()
    docling_result = {
        "pictures": [
            {"image": {"uri": f"data:image/png;base64,{b64}"}, "prov": [{"page_no": 1}]},
            {"image": {"uri": f"data:image/png;base64,{b64}"}, "prov": [{"page_no": 2}]},
        ]
    }

    images = _extract_and_save_images(docling_result, doc_id="test123", base_dir=tmp_path)

    assert len(images) == 2
    assert images[0]["image_id"] == "test123_page1_img0"
    assert images[1]["image_id"] == "test123_page2_img1"
    # Files should exist on disk
    assert Path(images[0]["path"]).exists()
    assert Path(images[1]["path"]).exists()
    # Should be JPEG
    assert images[0]["path"].endswith(".jpg")


def test_extract_and_save_images_empty_pictures():
    """Should return empty list when no pictures in Docling result."""
    from services.admin_endpoints import _extract_and_save_images

    images = _extract_and_save_images({}, doc_id="test456")
    assert images == []


def test_extract_and_save_images_skips_bad_base64(tmp_path):
    """Should skip images with invalid base64 and continue."""
    from services.admin_endpoints import _extract_and_save_images

    b64 = _make_test_png_b64()
    docling_result = {
        "pictures": [
            {"image": {"uri": "data:image/png;base64,INVALID!!!"}, "prov": [{"page_no": 1}]},
            {"image": {"uri": f"data:image/png;base64,{b64}"}, "prov": [{"page_no": 1}]},
        ]
    }

    images = _extract_and_save_images(docling_result, doc_id="test789", base_dir=tmp_path)

    # Should have 1 image (skipped the bad one)
    assert len(images) == 1
    assert images[0]["image_id"] == "test789_page1_img1"


def test_hierarchical_chunk_links_images_to_chunks():
    """Images should be linked to chunks based on placeholder positions."""
    from services.admin_endpoints import _hierarchical_chunk

    # Markdown with image placeholders at known positions
    md_text = "First section text here.\n\n<!-- image -->\n\nSecond section after image."
    docling_result = {"md": md_text}

    images = [
        {"image_id": "doc1_page1_img0", "path": "/tmp/img0.jpg", "page": "1"},
    ]

    chunks = _hierarchical_chunk(
        docling_result,
        source_file="test.pdf",
        domain="mold",
        uploaded_by="test",
        images=images,
    )

    assert len(chunks) > 0
    # At least one chunk should have the image linked
    linked = [c for c in chunks if c["metadata"].get("has_images")]
    assert len(linked) >= 1
    assert "doc1_page1_img0" in linked[0]["metadata"]["image_ids"]
    assert linked[0]["metadata"]["image_count"] == 1


def test_hierarchical_chunk_no_images_keeps_has_images_false():
    """Without images, has_images should remain False."""
    from services.admin_endpoints import _hierarchical_chunk

    chunks = _hierarchical_chunk(
        {"md": "Some text content."},
        source_file="test.pdf",
        domain="mold",
        uploaded_by="test",
    )

    assert len(chunks) > 0
    for c in chunks:
        assert c["metadata"]["has_images"] is False
        assert c["metadata"].get("image_ids", []) == []


@pytest.mark.asyncio
async def test_image_endpoint_returns_file(tmp_path):
    """_resolve_image_path should resolve a valid image_id to its file path."""
    from PIL import Image

    # Create a test image on disk
    doc_dir = tmp_path / "testdoc123"
    doc_dir.mkdir()
    img_path = doc_dir / "page1_img0.jpg"
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    img.save(img_path, "JPEG")

    from services.admin_endpoints import _resolve_image_path

    with patch("services.admin_endpoints.IMAGE_DIR", tmp_path):
        result = _resolve_image_path("testdoc123_page1_img0")
        assert result is not None
        assert result.exists()


def test_resolve_image_path_returns_none_for_missing():
    """Should return None for unknown image_id."""
    from services.admin_endpoints import _resolve_image_path

    result = _resolve_image_path("nonexistent_page99_img99")
    assert result is None
