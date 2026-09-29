from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """The chunk an ontology change was derived from."""

    path: Path
    chunk_id: str


class ProvenanceEvent(BaseModel):
    """One line of the provenance log: a single ontology change.

    `timestamp` and `mode` are stamped by the log, not by the caller, because
    both describe the build the event belongs to rather than the change itself.
    """

    event: str
    id: str
    source_documents: list[SourceRef] = Field(default_factory=list)
    source_excerpt: str = ""
    timestamp: str
    mode: str
    reason: str | None = None
    merged_ids: list[str] | None = None


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProvenanceLog:
    """Append-only JSONL event log for one build; one event per line.

    The file is created on the first record, and a log is never truncated, so
    events already on disk survive a later run that appends to the same file.
    """

    def __init__(self, path: Path, mode: str) -> None:
        self._path = path
        self._mode = mode

    def record(
        self,
        event: str,
        id: str,
        source_excerpt: str = "",
        source_documents: list[SourceRef] | None = None,
        *,
        reason: str | None = None,
        merged_ids: list[str] | None = None,
    ) -> None:
        """Append one event, stamped with the current time and the build mode."""
        entry = ProvenanceEvent(
            event=event,
            id=id,
            source_documents=source_documents or [],
            source_excerpt=source_excerpt,
            timestamp=_utc_timestamp(),
            mode=self._mode,
            reason=reason,
            merged_ids=merged_ids,
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(f"{entry.model_dump_json(exclude_none=True)}\n")
