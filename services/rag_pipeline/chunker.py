"""Text chunking module for RAG pipeline.

This module provides functionality to split documents into fixed-size chunks
with overlap for optimal retrieval in RAG systems.
"""

from typing import Any, Dict, List, Optional

import tiktoken


class TextChunker:
    """Splits text into fixed-size chunks with overlap using tiktoken.

    Uses cl100k_base encoding (GPT-like tokenization) to ensure accurate
    token counting for LLM context windows.

    Attributes:
        chunk_size: Maximum number of tokens per chunk (default: 512)
        overlap_percentage: Percentage of overlap between chunks (default: 0.2)
        encoding: tiktoken encoding instance for token counting
    """

    def __init__(self, chunk_size: int = 512, overlap_percentage: float = 0.2):
        """Initialize the TextChunker.

        Args:
            chunk_size: Maximum tokens per chunk (default: 512)
            overlap_percentage: Overlap between chunks as decimal (default: 0.2 = 20%)

        Raises:
            ValueError: If chunk_size <= 0 or overlap_percentage not in [0, 1)
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= overlap_percentage < 1:
            raise ValueError("overlap_percentage must be in range [0, 1)")

        self.chunk_size = chunk_size
        self.overlap_percentage = overlap_percentage
        self.overlap_tokens = int(chunk_size * overlap_percentage)

        # Use cl100k_base encoding (same as GPT-3.5/GPT-4)
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def chunk_text(
        self, text: str, section: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Split text into chunks with overlap.

        Args:
            text: Input text to chunk
            section: Optional section header/title for this text. When provided,
                all chunks will include this section information in their metadata.

        Returns:
            List of chunk dictionaries with structure:
            {
                "text": str,           # Chunk text content
                "chunk_id": int,       # Sequential chunk ID (0-indexed)
                "start_char": int,     # Start character position in original text
                "end_char": int,       # End character position in original text
                "token_count": int,    # Number of tokens in this chunk
                "section": Optional[str]  # Section header if provided
            }

        Examples:
            >>> chunker = TextChunker(chunk_size=512, overlap_percentage=0.2)
            >>> chunks = chunker.chunk_text("Long document text...")
            >>> print(chunks[0]["token_count"])
            512
            >>> chunks = chunker.chunk_text("Section text...", section="Introduction")
            >>> print(chunks[0]["section"])
            'Introduction'
        """
        # Handle empty text
        if not text or not text.strip():
            return []

        # Encode entire text to tokens
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        # If text is shorter than chunk_size, return as single chunk
        if total_tokens <= self.chunk_size:
            return [{
                "text": text,
                "chunk_id": 0,
                "start_char": 0,
                "end_char": len(text),
                "token_count": total_tokens,
                "section": section
            }]

        chunks = []
        chunk_id = 0
        start_token_idx = 0
        current_char_pos = 0

        # Calculate step size (chunk_size - overlap)
        step_size = self.chunk_size - self.overlap_tokens

        while start_token_idx < total_tokens:
            # Calculate end token index for this chunk
            end_token_idx = min(start_token_idx + self.chunk_size, total_tokens)

            # Extract token slice for this chunk
            chunk_tokens = tokens[start_token_idx:end_token_idx]

            # Decode tokens back to text
            chunk_text = self.encoding.decode(chunk_tokens)

            # Calculate character positions incrementally
            # For the first chunk, start_char is 0 (already set by current_char_pos)
            # For subsequent chunks, we need to account for overlap
            start_char = current_char_pos
            end_char = current_char_pos + len(chunk_text)

            # Create chunk dictionary
            chunks.append({
                "text": chunk_text,
                "chunk_id": chunk_id,
                "start_char": start_char,
                "end_char": end_char,
                "token_count": len(chunk_tokens),
                "section": section
            })

            # Update character position for next chunk
            # Only advance by the non-overlapping portion (step_size tokens)
            if start_token_idx + step_size < total_tokens:
                # Decode the step_size tokens to find how many chars to advance
                step_tokens = tokens[start_token_idx:start_token_idx + step_size]
                current_char_pos += len(self.encoding.decode(step_tokens))
            else:
                # Last chunk, no need to update position
                current_char_pos = end_char

            # Move to next chunk position
            start_token_idx += step_size
            chunk_id += 1

            # Break if we've processed all tokens
            if end_token_idx >= total_tokens:
                break

        return chunks
