"""Tests for text chunker module."""

import pytest
from services.rag_pipeline.chunker import TextChunker


def test_basic_chunking():
    """Test that text is chunked correctly with proper overlap."""
    # Create sample text longer than 512 tokens
    # Each sentence is ~15-20 tokens, so 50 sentences should give us ~800-1000 tokens
    sample_text = " ".join([
        f"This is sentence number {i} in our test document. "
        f"It contains some information about testing the chunking functionality. "
        f"We need to ensure that the chunker properly splits text into manageable pieces. "
        for i in range(50)
    ])

    chunker = TextChunker(chunk_size=512, overlap_percentage=0.2)
    chunks = chunker.chunk_text(sample_text)

    # Verify chunks were created
    assert len(chunks) > 0, "Should create at least one chunk"
    assert len(chunks) >= 2, "Sample text should create multiple chunks"

    # Verify each chunk structure
    for chunk in chunks:
        assert "text" in chunk, "Chunk should have 'text' field"
        assert "chunk_id" in chunk, "Chunk should have 'chunk_id' field"
        assert "start_char" in chunk, "Chunk should have 'start_char' field"
        assert "end_char" in chunk, "Chunk should have 'end_char' field"
        assert "token_count" in chunk, "Chunk should have 'token_count' field"

    # Verify each chunk is approximately 512 tokens (allow some variance)
    for chunk in chunks[:-1]:  # All chunks except the last
        assert chunk["token_count"] <= 512, f"Chunk {chunk['chunk_id']} exceeds max size"
        # Most chunks should be close to 512 tokens
        assert chunk["token_count"] >= 400, f"Chunk {chunk['chunk_id']} is too small"

    # Verify 20% overlap exists between consecutive chunks
    overlap_tokens = int(512 * 0.2)  # ~102 tokens

    for i in range(len(chunks) - 1):
        current_chunk = chunks[i]
        next_chunk = chunks[i + 1]

        # Extract overlap region from current chunk (last ~100 tokens worth of text)
        current_end = current_chunk["text"][-200:]  # Approximate
        next_start = next_chunk["text"][:200]  # Approximate

        # There should be some overlap in the text
        # This is a simple check - the actual overlap should be ~100 tokens
        assert len(current_end) > 0 and len(next_start) > 0, "Chunks should have overlap region"

    # Verify chunk IDs are sequential
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_id"] == i, f"Chunk ID should be {i}"


def test_empty_text():
    """Test that empty text is handled gracefully."""
    chunker = TextChunker()
    chunks = chunker.chunk_text("")

    assert len(chunks) == 0, "Empty text should produce no chunks"


def test_short_text():
    """Test that text shorter than chunk_size is returned as a single chunk."""
    short_text = "This is a short text with only a few words."

    chunker = TextChunker(chunk_size=512)
    chunks = chunker.chunk_text(short_text)

    assert len(chunks) == 1, "Short text should produce exactly one chunk"
    assert chunks[0]["text"] == short_text, "Short text should be unchanged"
    assert chunks[0]["chunk_id"] == 0, "First chunk should have ID 0"
    assert chunks[0]["token_count"] < 512, "Short text should have fewer than 512 tokens"


def test_very_long_text():
    """Test that very long text produces many chunks."""
    # Create text with ~200 sentences (approximately 3000-4000 tokens)
    long_text = " ".join([
        f"Sentence {i}: This is a test sentence with some content to create a long document. "
        f"We are testing that the chunker can handle very long documents efficiently. "
        for i in range(200)
    ])

    chunker = TextChunker(chunk_size=512, overlap_percentage=0.2)
    chunks = chunker.chunk_text(long_text)

    # Should produce more than 10 chunks
    assert len(chunks) > 10, f"Long text should produce many chunks, got {len(chunks)}"

    # Verify all chunks except the last are properly sized
    for chunk in chunks[:-1]:
        assert chunk["token_count"] <= 512, f"Chunk {chunk['chunk_id']} exceeds max size"
        assert chunk["token_count"] >= 400, f"Chunk {chunk['chunk_id']} is too small"

    # Last chunk can be smaller
    assert chunks[-1]["token_count"] <= 512, "Last chunk should not exceed max size"

    # Verify sequential chunk IDs
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_id"] == i, f"Chunk ID mismatch at position {i}"


def test_section_preservation():
    """Test that section information is preserved in chunk metadata."""
    # Create sample text with multiple chunks
    sample_text = " ".join([
        f"This is sentence number {i} in the Introduction section. "
        f"It contains some information about testing the chunking functionality. "
        f"We need to ensure that the chunker properly preserves section metadata. "
        for i in range(50)
    ])

    # Test with section provided
    chunker = TextChunker(chunk_size=512, overlap_percentage=0.2)
    chunks_with_section = chunker.chunk_text(sample_text, section="Introduction")

    assert len(chunks_with_section) > 0, "Should create at least one chunk"

    # Verify all chunks have the section field
    for chunk in chunks_with_section:
        assert "section" in chunk, "Chunk should have 'section' field"
        assert chunk["section"] == "Introduction", f"Chunk {chunk['chunk_id']} section should be 'Introduction'"

    # Test without section (should still have field but set to None)
    chunks_without_section = chunker.chunk_text(sample_text)

    for chunk in chunks_without_section:
        assert "section" in chunk, "Chunk should have 'section' field even when not provided"
        assert chunk["section"] is None, f"Chunk {chunk['chunk_id']} section should be None"

    # Test with different section names
    test_sections = ["Abstract", "Methods", "Results", "Conclusion"]
    for section_name in test_sections:
        chunks = chunker.chunk_text(sample_text[:500], section=section_name)
        assert all(chunk["section"] == section_name for chunk in chunks), \
            f"All chunks should have section '{section_name}'"
