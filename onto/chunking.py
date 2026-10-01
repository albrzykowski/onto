import re
from pathlib import Path

from pydantic import BaseModel

from onto.config import BuilderConfig
from onto.ingestion import Document
from onto.provenance import SourceRef

TOKEN_PATTERN = re.compile(r"\S+")


class Chunk(BaseModel):
    """A size-limited slice of a document, ready to be sent to the LLM.

    `source_path` is where the document is and `source_name` is what the ontology calls it.
    The two differ whenever a build is pointed at a corpus by an absolute path, and only the
    second one is written anywhere, so that the schema and the provenance log of one corpus
    read the same wherever the build was run.
    """

    chunk_id: str
    text: str
    source_path: Path
    source_name: str
    token_count: int

    def source_ref(self) -> SourceRef:
        """The chunk as a provenance reference: the document the ontology calls it, and which
        chunk of that document it is."""
        return SourceRef(path=Path(self.source_name), chunk_id=self.chunk_id)


def document_name(path: Path) -> str:
    """How the ontology names a document: its path as the build was pointed at it, relative
    to the working directory whenever the document lies there.

    The name goes into the schema and into the provenance log, so a name built from an
    absolute path would write the build machine's directory layout into artifacts that get
    committed and shared, and would make the same corpus produce a different schema from a
    different directory. A document outside the working directory has no relative name, and
    the path the caller gave is the only truthful one to record.
    """
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


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
    """Split a document into overlapping, size-limited chunks.

    The strategy and the window bounds are validated when the configuration is loaded, so
    a BuilderConfig reaching this point is already known to be splittable.
    """
    size = config.max_chunk_tokens
    step = size - config.overlap_tokens

    tokens = tokenize(document.text)
    if not tokens:
        return []

    name = document_name(document.path)
    chunks: list[Chunk] = []
    start = 0
    while True:
        window = tokens[start : start + size]
        chunks.append(
            Chunk(
                chunk_id=f"{name}#c{len(chunks) + 1}",
                text=" ".join(window),
                source_path=document.path,
                source_name=name,
                token_count=len(window),
            )
        )
        if start + size >= len(tokens):
            break
        start += step
    return chunks
