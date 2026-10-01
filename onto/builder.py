"""Orchestration of a build: documents in, ontology out."""

import json
import logging
from pathlib import Path

from onto.chunking import Chunk, chunk_document
from onto.config import BuilderConfig
from onto.dedup import Embedder
from onto.extraction import extract
from onto.ingestion import Document, load_documents
from onto.instance_gen import extend_instances, generate_abox
from onto.llm import LLM
from onto.provenance import ProvenanceLog
from onto.schema_gen import SCHEMA_FILE_NAME, generate_tbox, update_tbox

logger = logging.getLogger(__name__)

STATE_FILE_NAME = "state.json"
PROVENANCE_FILE_NAME = "provenance.jsonl"

OVERRIDE = "override"
UPDATE = "update"

_SKIPPED = "document.skipped"
_UNCHANGED = "unchanged_fingerprint"


class BuildError(Exception):
    """Raised when a build cannot run in the configured mode."""


def _write_state(fingerprints: dict[str, str], output_dir: Path) -> Path:
    path = output_dir / STATE_FILE_NAME
    path.write_text(json.dumps(fingerprints, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_state(output_dir: Path) -> dict[str, str]:
    path = output_dir / STATE_FILE_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _fingerprints(documents: list[Document], input_dir: Path) -> dict[str, str]:
    """Documents are keyed by their name inside the input directory: an absolute path would
    make the state of the same corpus depend on where the corpus happens to live."""
    return {document.path.relative_to(input_dir).as_posix(): document.fingerprint
            for document in documents}


def _unread(
    documents: list[Document], state: dict[str, str], input_dir: Path, log: ProvenanceLog
) -> list[Document]:
    """The documents an earlier build has not read: a document the state already records
    under the same fingerprint is left alone, and logged, so re-running costs nothing."""
    unread = []
    for document in documents:
        name = document.path.relative_to(input_dir).as_posix()
        if state.get(name) == document.fingerprint:
            log.record(event=_SKIPPED, id=name, reason=_UNCHANGED)
            continue
        unread.append(document)
    return unread


def _chunks_of(documents: list[Document], config: BuilderConfig) -> list[Chunk]:
    return [chunk for document in documents for chunk in chunk_document(document, config)]


def build(
    input_dir: Path,
    output_dir: Path,
    config: BuilderConfig,
    llm: LLM,
    embedder: Embedder | None = None,
) -> None:
    """Build the ontology of `input_dir` into `output_dir`.

    Override mode keeps nothing of an earlier build: the schema, the instances and the state
    describe the documents at hand alone. The provenance log of the replaced build is removed
    with them — the log belongs to the build that wrote it, and a log that survived would
    claim the new ontology was derived from the old one's sources.

    Update mode extends what is already there. Only the documents whose fingerprint the state
    does not record are read again, and the log of the earlier build is kept and appended to,
    so the events of one build still say which build they belong to.
    """
    if config.mode == OVERRIDE:
        _override(input_dir, output_dir, config, llm)
    elif config.mode == UPDATE:
        if embedder is None:
            raise BuildError(
                "update mode needs an embedder: it cannot tell a repeated concept from a new "
                "one without one"
            )
        _update(input_dir, output_dir, config, llm, embedder)
    else:
        raise BuildError(f"unsupported mode: {config.mode!r}")


def _override(input_dir: Path, output_dir: Path, config: BuilderConfig, llm: LLM) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / PROVENANCE_FILE_NAME
    log_path.unlink(missing_ok=True)
    log = ProvenanceLog(log_path, config.mode)

    documents = load_documents(input_dir)
    chunks = _chunks_of(documents, config)
    candidates = extract(chunks, config, llm)
    schema_path = generate_tbox(candidates, config, llm, output_dir, log)
    generate_abox(chunks, config, llm, schema_path, log)
    _write_state(_fingerprints(documents, input_dir), output_dir)
    logger.info("built %s from %s documents", output_dir, len(documents))


def _update(
    input_dir: Path, output_dir: Path, config: BuilderConfig, llm: LLM, embedder: Embedder
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log = ProvenanceLog(output_dir / PROVENANCE_FILE_NAME, config.mode)

    state = _read_state(output_dir)
    documents = _unread(load_documents(input_dir), state, input_dir, log)
    if not documents:
        logger.info("no document new since the last build of %s", output_dir)
        return

    chunks = _chunks_of(documents, config)
    candidates = extract(chunks, config, llm)
    schema_path = update_tbox(
        candidates, output_dir / SCHEMA_FILE_NAME, config, llm, log, embedder
    )
    extend_instances(chunks, config, llm, schema_path, log)
    _write_state({**state, **_fingerprints(documents, input_dir)}, output_dir)
    logger.info("extended %s with %s documents", output_dir, len(documents))
