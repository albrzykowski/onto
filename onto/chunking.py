import re
from pathlib import Path

from pydantic import BaseModel

from onto.config import BuilderConfig
from onto.ingestion import Document

_FIXED = "fixed"

TOKEN_PATTERN = re.compile(r"\S+")


class ChunkError(Exception):
    """Raised when a document cannot be split into chunks."""


class Chunk(BaseModel):
    """A size-limited slice of a document, ready to be sent to the LLM."""

    chunk_id: str
    text: str
    source_path: Path
    token_count: int


def tokenize(text: str) -> list[str]:
    """Split text into tokens.

    Whitespace-delimited words are used as the token unit. This is an
    approximation: a real tokenizer for the target model would be more
    accurate, so this is the single place to swap when one is available.
    """
    return TOKEN_PATTERN.findall(text)


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def chunk_document(document: Document, config: BuilderConfig) -> list[Chunk]:
    """Split a document into overlapping, size-limited chunks."""
    if config.chunking_strategy != _FIXED:
        raise ChunkError(f"unsupported chunking strategy: {config.chunking_strategy!r}")

    size = config.max_chunk_tokens
    overlap = config.overlap_tokens
    if size < 1:
        raise ChunkError(f"max_chunk_tokens must be at least 1, got {size}")
    if not 0 <= overlap < size:
        raise ChunkError(
            f"overlap_tokens must be between 0 and {size - 1}, got {overlap}"
        )

    tokens = tokenize(document.text)
    if not tokens:
        return []

    step = size - overlap
    chunks: list[Chunk] = []
    start = 0
    while True:
        window = tokens[start : start + size]
        chunks.append(
            Chunk(
                chunk_id=f"{document.path}#c{len(chunks) + 1}",
                text=" ".join(window),
                source_path=document.path,
                token_count=len(window),
            )
        )
        if start + size >= len(tokens):
            break
        start += step
    return chunks
