"""Orchestration of a build: documents in, ontology out."""

import json
import logging
from pathlib import Path

from onto.chunking import chunk_document
from onto.config import BuilderConfig
from onto.extraction import extract
from onto.ingestion import Document, load_documents
from onto.instance_gen import generate_abox
from onto.llm import LLM
from onto.provenance import ProvenanceLog
from onto.schema_gen import generate_tbox

logger = logging.getLogger(__name__)

STATE_FILE_NAME = "state.json"
PROVENANCE_FILE_NAME = "provenance.jsonl"

OVERRIDE = "override"


class BuildError(Exception):
    """Raised when a build cannot run in the configured mode."""


def _write_state(documents: list[Document], input_dir: Path, output_dir: Path) -> Path:
    """Record what this build read, so a later run can tell what it has already seen.

    Documents are keyed by their name inside the input directory: an absolute path would
    make the state of the same corpus depend on where the corpus happens to live.
    """
    fingerprints = {
        document.path.relative_to(input_dir).as_posix(): document.fingerprint
        for document in documents
    }
    path = output_dir / STATE_FILE_NAME
    path.write_text(json.dumps(fingerprints, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build(input_dir: Path, output_dir: Path, config: BuilderConfig, llm: LLM) -> None:
    """Build the ontology of `input_dir` into `output_dir`, discarding whatever was there.

    Override mode keeps nothing of an earlier build: the schema, the instances and the state
    describe the documents at hand alone. The provenance log of the replaced build is removed
    with them — the log belongs to the build that wrote it, and a log that survived would
    claim the new ontology was derived from the old one's sources.
    """
    if config.mode != OVERRIDE:
        raise BuildError(
            f"{config.mode!r} mode is not implemented: this builder rebuilds from scratch"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / PROVENANCE_FILE_NAME
    log_path.unlink(missing_ok=True)
    log = ProvenanceLog(log_path, config.mode)

    documents = load_documents(input_dir)
    chunks = [chunk for document in documents for chunk in chunk_document(document, config)]
    candidates = extract(chunks, config, llm)
    schema_path = generate_tbox(candidates, config, llm, output_dir)
    generate_abox(chunks, config, llm, schema_path, log)
    _write_state(documents, input_dir, output_dir)
    logger.info("built %s from %s documents", output_dir, len(documents))
