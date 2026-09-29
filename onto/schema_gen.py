import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from onto.config import BuilderConfig
from onto.extraction import Candidate, CandidateKind
from onto.llm import LLM, CompletionRequest

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096
SCHEMA_FILE_NAME = "schema.yaml"
SCHEMA_NAMESPACE = "https://example.org"

_INSTRUCTIONS = """You are an ontology engineer designing a LinkML schema from concepts that \
were extracted from a corpus.

Rules:
- Describe every class in one sentence, in English, stating what the corpus says it is.
- Assign each class only the slots that describe it; leave a class without slots if none fit.
- Use only the class and slot names you are given; invent nothing.

Answer with a single JSON object and nothing else:
{"classes": {"Vehicle": {"description": ..., "slots": ["has_engine"]}}}"""


class _PlannedClass(BaseModel):
    description: str
    slots: list[str] = Field(default_factory=list)


class _Plan(BaseModel):
    classes: dict[str, _PlannedClass] = Field(default_factory=dict)


class _Annotation(BaseModel):
    tag: str
    value: list[str]


class _Provenance(BaseModel):
    source_documents: _Annotation


class _ClassDefinition(BaseModel):
    name: str
    description: str
    slots: list[str] = Field(default_factory=list)
    annotations: _Provenance


class _SlotDefinition(BaseModel):
    name: str
    annotations: _Provenance


class _Schema(BaseModel):
    """The subset of LinkML the generated T-Box uses."""

    id: str
    name: str
    prefixes: dict[str, str]
    default_prefix: str
    default_range: str
    imports: list[str]
    classes: dict[str, _ClassDefinition]
    slots: dict[str, _SlotDefinition]


def _consolidate(candidates: list[Candidate], kind: CandidateKind) -> dict[str, list[str]]:
    """Merge the candidates of one kind by name, keeping every chunk they came from."""
    consolidated: dict[str, list[str]] = {}
    for candidate in candidates:
        if candidate.kind != kind:
            continue
        chunk_ids = consolidated.setdefault(candidate.name, [])
        chunk_ids.extend(
            source.chunk_id
            for source in candidate.source_documents
            if source.chunk_id not in chunk_ids
        )
    return consolidated


def _provenance(chunk_ids: list[str]) -> _Provenance:
    return _Provenance(source_documents=_Annotation(tag="source_documents", value=chunk_ids))


def _prompt(class_names: list[str], slot_names: list[str]) -> str:
    """The consolidated candidate names, in extraction order; the LLM may only use these."""
    listing = [
        f"Candidate classes: {', '.join(class_names) or 'none'}",
        f"Candidate slots: {', '.join(slot_names) or 'none'}",
    ]
    return "\n\n".join([_INSTRUCTIONS, *listing])


def _plan(llm: LLM, class_names: list[str], slot_names: list[str], config: BuilderConfig) -> _Plan:
    reply = llm.complete(
        CompletionRequest(
            model=config.model, prompt=_prompt(class_names, slot_names), max_tokens=_MAX_TOKENS
        )
    )
    return _Plan.model_validate_json(reply)


def _classes(
    consolidated: dict[str, list[str]], known_slots: dict[str, list[str]], plan: _Plan
) -> dict[str, _ClassDefinition]:
    """A class the model left out of its plan is not part of the schema."""
    definitions = {}
    for name, chunk_ids in consolidated.items():
        planned = plan.classes.get(name)
        if planned is None:
            continue
        definitions[name] = _ClassDefinition(
            name=name,
            description=planned.description,
            slots=[slot for slot in planned.slots if slot in known_slots],
            annotations=_provenance(chunk_ids),
        )
    return definitions


def generate_tbox(
    candidates: list[Candidate], config: BuilderConfig, llm: LLM, output_dir: Path
) -> Path:
    """Write the T-Box of the extracted candidates as a LinkML schema.

    Every candidate that proposed the same name is consolidated into a single definition
    whose `source_documents` annotation lists the chunks it was read from. The schema is
    named after the output directory, so writing into `ontology/` yields `ontology-schema`.
    """
    class_sources = _consolidate(candidates, "class")
    slot_sources = _consolidate(candidates, "relation")
    plan = _plan(llm, list(class_sources), list(slot_sources), config)
    name = f"{output_dir.name}-schema"
    schema = _Schema(
        id=f"{SCHEMA_NAMESPACE}/{name}",
        name=name,
        prefixes={output_dir.name: f"{SCHEMA_NAMESPACE}/{output_dir.name}/"},
        default_prefix=output_dir.name,
        default_range="string",
        imports=["linkml:types"],
        classes=_classes(class_sources, slot_sources, plan),
        slots={
            slot: _SlotDefinition(name=slot, annotations=_provenance(chunk_ids))
            for slot, chunk_ids in slot_sources.items()
        },
    )
    path = output_dir / SCHEMA_FILE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(schema.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    logger.info("wrote %s with %s classes", path, len(schema.classes))
    return path
