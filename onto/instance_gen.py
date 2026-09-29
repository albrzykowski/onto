import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from onto.chunking import Chunk
from onto.config import BuilderConfig
from onto.llm import LLM, CompletionRequest
from onto.provenance import ProvenanceLog, SourceRef

logger = logging.getLogger(__name__)

INSTANCES_FILE_NAME = "instances.yaml"

_MAX_TOKENS = 4096
_REJECTED = "instance.rejected"
_NOT_IN_TBOX = "not_in_tbox"

_INSTRUCTIONS = """You are an ontology engineer. Read the source text and name the concrete \
entities it states, as instances of the classes listed below.

Rules:
- Name every entity the text states concretely, and skip what it merely mentions in passing.
- Give each slot the name of the entity it points to, written exactly as the text writes it.
- Use only the classes and slots listed below; invent nothing.
- Copy the excerpt verbatim from the source text; it is the only proof of where the \
instance came from.

Answer with a single JSON object and nothing else:
{"instances": [{"name": ..., "class": ..., "slots": {...}, "excerpt": ...}]}"""


class Instance(BaseModel):
    """A concrete fact stated by the corpus: an entity of one of the T-Box classes."""

    id: str
    class_name: str
    slot_values: dict[str, str] = Field(default_factory=dict)
    source_documents: list[SourceRef] = Field(default_factory=list)
    source_excerpt: str = ""


class _Proposal(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    class_name: str = Field(alias="class")
    slots: dict[str, str] = Field(default_factory=dict)
    excerpt: str = ""


class _Answer(BaseModel):
    instances: list[_Proposal] = Field(default_factory=list)


def _identifier(name: str) -> str:
    """An instance, and every value pointing at one, is written as a single token."""
    return "_".join(name.split())


def _classes_of(schema_path: Path) -> dict[str, list[str]]:
    """The classes and their slots as the written T-Box defines them."""
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    return {
        name: list(definition.get("slots", []))
        for name, definition in schema["classes"].items()
    }


def _listing(classes: dict[str, list[str]]) -> str:
    return "\n".join(
        f"- {name}: {', '.join(slots)}" if slots else f"- {name}" for name, slots in classes.items()
    )


def _prompt(classes: dict[str, list[str]], chunk: Chunk) -> str:
    sections = [
        _INSTRUCTIONS,
        f"Classes of the schema:\n{_listing(classes)}",
        f"Source text:\n[{chunk.chunk_id}]\n{chunk.text}",
    ]
    return "\n\n".join(sections)


def _proposals(
    llm: LLM, config: BuilderConfig, classes: dict[str, list[str]], chunk: Chunk
) -> list[_Proposal]:
    reply = llm.complete(
        CompletionRequest(
            model=config.model, prompt=_prompt(classes, chunk), max_tokens=_MAX_TOKENS
        )
    )
    return _Answer.model_validate_json(reply).instances


def _instance(proposal: _Proposal, slots: list[str], chunk: Chunk) -> Instance:
    return Instance(
        id=_identifier(proposal.name),
        class_name=proposal.class_name,
        slot_values={
            slot: _identifier(value) for slot, value in proposal.slots.items() if slot in slots
        },
        source_documents=[SourceRef(path=chunk.source_path, chunk_id=chunk.chunk_id)],
        source_excerpt=proposal.excerpt,
    )


def _entry(instance: Instance) -> dict[str, Any]:
    """One instance as written: its class, the slot values stated for it, and its provenance."""
    return {
        "class": instance.class_name,
        **instance.slot_values,
        "annotations": {
            "source_documents": {
                "tag": "source_documents",
                "value": [source.chunk_id for source in instance.source_documents],
            },
            "source_excerpt": {"tag": "source_excerpt", "value": instance.source_excerpt},
        },
    }


def generate_abox(
    chunks: list[Chunk],
    config: BuilderConfig,
    llm: LLM,
    schema_path: Path,
    log: ProvenanceLog,
) -> Path:
    """Write the instances the corpus states as an A-Box next to the T-Box at
    `instances.yaml`, and return the path written.

    The T-Box is the only vocabulary: an instance of a class the schema does not define is
    rejected and logged rather than written, and a slot the class does not have is dropped.
    Every written instance carries the chunk and the excerpt it was read from. Each chunk
    is one request; a failure is logged and the chunk skipped, so one bad chunk never
    aborts the build — the catch is deliberately wider, because an adapter that lets a
    provider's own exception escape would otherwise take the whole build down.
    """
    classes = _classes_of(schema_path)
    instances: dict[str, Instance] = {}
    for chunk in chunks:
        try:
            proposals = _proposals(llm, config, classes, chunk)
        except Exception as error:
            logger.error("instance extraction failed for %s: %s", chunk.chunk_id, error)
            continue
        for proposal in proposals:
            if proposal.class_name not in classes:
                log.record(
                    event=_REJECTED,
                    id=_identifier(proposal.name),
                    source_excerpt=proposal.excerpt,
                    source_documents=[SourceRef(path=chunk.source_path, chunk_id=chunk.chunk_id)],
                    reason=_NOT_IN_TBOX,
                )
                continue
            instance = _instance(proposal, classes[proposal.class_name], chunk)
            # a later chunk stating the same entity replaces the earlier one
            instances[instance.id] = instance
    path = schema_path.parent / INSTANCES_FILE_NAME
    path.write_text(
        yaml.safe_dump(
            {"instances": {key: _entry(value) for key, value in instances.items()}},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    logger.info("wrote %s with %s instances", path, len(instances))
    return path
