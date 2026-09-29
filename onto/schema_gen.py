import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from onto.config import BuilderConfig
from onto.dedup import Embedder, closest_of, verify_merge
from onto.extraction import Candidate, CandidateKind
from onto.llm import LLM, CompletionRequest
from onto.provenance import ProvenanceLog, SourceRef

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096
SCHEMA_FILE_NAME = "schema.yaml"
SCHEMA_NAMESPACE = "https://example.org"

_MERGED = "class.merged"
_SLOT_UPDATED = "slot.updated"

_INSTRUCTIONS = """You are an ontology engineer designing a LinkML schema from concepts that \
were extracted from a corpus.

Rules:
- Describe every class in one sentence, in English, stating what the corpus says it is.
- Assign each class only the slots that describe it; leave a class without slots if none fit.
- Use only the class and slot names you are given; invent nothing.

Answer with a single JSON object and nothing else:
{"classes": {"Vehicle": {"description": ..., "slots": ["has_engine"]}}}"""

_UPDATE_INSTRUCTIONS = """You are an ontology engineer extending an existing LinkML schema with \
concepts extracted from new documents.

Rules:
- Describe every new class in one sentence, in English, stating what the corpus says it is.
- Assign each class only the slots that describe it; leave a class without slots if none fit.
- Name the class a new one is a kind of under "is_a"; leave it out when it is a kind of none.
- Use only the class and slot names you are given; invent nothing.

Answer with a single JSON object and nothing else:
{"classes": {"Transmission": {"description": ..., "slots": ["has_gearbox"], "is_a": "Vehicle"}},
 "slot_ranges": {"has_gearbox": "integer"}}"""

_RESOLVE_INSTRUCTIONS = """You are an ontology engineer. A slot of an existing schema is \
already in use with one type, and the new documents describe its value with another.

Rules:
- Answer with the single type the slot keeps, the one that fits every use described.
- Use one of the offered types; invent no other.

Answer with a single JSON object and nothing else:
{"range": "integer"}"""


class _PlannedClass(BaseModel):
    description: str
    slots: list[str] = Field(default_factory=list)
    is_a: str | None = None


class _Plan(BaseModel):
    classes: dict[str, _PlannedClass] = Field(default_factory=dict)


class _UpdatePlan(_Plan):
    slot_ranges: dict[str, str] = Field(default_factory=dict)


class _Resolution(BaseModel):
    range: str


class _Annotation(BaseModel):
    tag: str
    value: list[str]


class _Provenance(BaseModel):
    source_documents: _Annotation


class _ClassDefinition(BaseModel):
    name: str
    description: str
    slots: list[str] = Field(default_factory=list)
    is_a: str | None = None
    annotations: _Provenance


class _SlotDefinition(BaseModel):
    name: str
    range: str | None = None
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


def _cite(definition: _Provenance, chunk_ids: list[str]) -> None:
    """Every chunk a definition was stated in is remembered, and a concept the corpus names
    again adds to that list rather than replacing what the ontology says about it."""
    cited = definition.source_documents.value
    cited.extend(chunk for chunk in chunk_ids if chunk not in cited)


def _write(schema: _Schema, path: Path) -> Path:
    """A slot range and a superclass are written only when the model stated them, so a class
    the corpus describes no parent of keeps the plain shape an earlier build gave it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(schema.model_dump(exclude_none=True), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("wrote %s with %s classes", path, len(schema.classes))
    return path


def _read(schema_path: Path) -> _Schema:
    return _Schema.model_validate(yaml.safe_load(schema_path.read_text(encoding="utf-8")))


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
    return _write(schema, output_dir / SCHEMA_FILE_NAME)


def _readings(
    candidates: list[Candidate], kind: CandidateKind, name: str
) -> tuple[list[SourceRef], str]:
    """Where one proposed concept was read: every chunk it came from, and the text of one."""
    matching = [
        candidate for candidate in candidates if candidate.kind == kind and candidate.name == name
    ]
    return (
        [source for candidate in matching for source in candidate.source_documents],
        matching[0].source_excerpt if matching else "",
    )


def _update_plan(
    llm: LLM, class_names: list[str], slot_names: list[str], config: BuilderConfig
) -> _UpdatePlan:
    """The model describes the new concepts, saying which existing class each is a kind of,
    so that a class is placed in the hierarchy instead of standing beside it."""
    listing = [
        f"New concepts: {', '.join(class_names) or 'none'}",
        f"New slots: {', '.join(slot_names) or 'none'}",
    ]
    reply = llm.complete(
        CompletionRequest(
            model=config.model,
            prompt="\n\n".join([_UPDATE_INSTRUCTIONS, *listing]),
            max_tokens=_MAX_TOKENS,
        )
    )
    return _UpdatePlan.model_validate_json(reply)


def _resolve_range(llm: LLM, config: BuilderConfig, slot: str, current: str, proposed: str) -> str:
    """A slot cannot hold two types at once, so the model is asked which of the two it keeps."""
    prompt = "\n\n".join(
        [
            _RESOLVE_INSTRUCTIONS,
            f"Slot: {slot}",
            f"Type already in use: {current}",
            f"Type the new documents propose: {proposed}",
        ]
    )
    reply = llm.complete(
        CompletionRequest(model=config.model, prompt=prompt, max_tokens=_MAX_TOKENS)
    )
    return _Resolution.model_validate_json(reply).range


def _duplicates(
    schema: _Schema,
    class_sources: dict[str, list[str]],
    candidates: list[Candidate],
    config: BuilderConfig,
    llm: LLM,
    log: ProvenanceLog,
    embedder: Embedder,
) -> set[str]:
    """The proposed classes that turned out to name a concept the schema already has.

    The class already in the ontology survives and cites the chunks the merged name was read
    from, so the schema keeps saying where the concept was stated. The merged name is never
    written: it is a second word for one concept, and a class stands for a concept.
    """
    pairs = closest_of(
        embedder, list(schema.classes), list(class_sources), config.similarity_threshold
    )
    duplicates = set()
    for name, (existing, _) in pairs.items():
        if not verify_merge(llm, config, existing, name):
            continue
        sources, excerpt = _readings(candidates, "class", name)
        _cite(schema.classes[existing].annotations, class_sources[name])
        log.record(
            event=_MERGED,
            id=existing,
            source_documents=sources,
            source_excerpt=excerpt,
            merged_ids=[name],
        )
        duplicates.add(name)
    return duplicates


def _add_classes(
    schema: _Schema,
    class_sources: dict[str, list[str]],
    slot_sources: dict[str, list[str]],
    duplicates: set[str],
    plan: _UpdatePlan,
) -> None:
    """The classes the model left out of its plan are not added, and neither are the ones
    merged into a class already there. A class the corpus names again keeps the description
    it has and cites the new chunk beside the old ones: a class is one concept, and a later
    document does not get to decide what it means. A `is_a` naming a class the schema will
    not have is dropped, because a superclass that is not there describes nothing."""
    known_slots = {*schema.slots, *slot_sources}
    known_classes = {*schema.classes, *class_sources} - duplicates
    for name, chunk_ids in class_sources.items():
        planned = plan.classes.get(name)
        if name in duplicates or planned is None:
            continue
        if name in schema.classes:
            _cite(schema.classes[name].annotations, chunk_ids)
            continue
        schema.classes[name] = _ClassDefinition(
            name=name,
            description=planned.description,
            slots=[slot for slot in planned.slots if slot in known_slots],
            is_a=planned.is_a if planned.is_a in known_classes else None,
            annotations=_provenance(chunk_ids),
        )


def _add_slots(
    schema: _Schema,
    slot_sources: dict[str, list[str]],
    candidates: list[Candidate],
    plan: _UpdatePlan,
    config: BuilderConfig,
    llm: LLM,
    log: ProvenanceLog,
) -> None:
    """A slot the new documents repeat is left as it is, except that it cites them too; a slot
    they give another type is put to the model, and the type it keeps is the one written."""
    for name, chunk_ids in slot_sources.items():
        proposed = plan.slot_ranges.get(name)
        known = schema.slots.get(name)
        if known is None:
            schema.slots[name] = _SlotDefinition(
                name=name, range=proposed, annotations=_provenance(chunk_ids)
            )
            continue
        _cite(known.annotations, chunk_ids)
        if proposed is None or known.range is None or proposed == known.range:
            continue
        known.range = _resolve_range(llm, config, name, known.range, proposed)
        sources, excerpt = _readings(candidates, "relation", name)
        log.record(event=_SLOT_UPDATED, id=name, source_documents=sources, source_excerpt=excerpt)


def update_tbox(
    candidates: list[Candidate],
    schema_path: Path,
    config: BuilderConfig,
    llm: LLM,
    log: ProvenanceLog,
    embedder: Embedder,
) -> Path:
    """Extend the schema written by an earlier build with what the new documents state, and
    return the path written.

    The schema is never rebuilt from scratch: what it already defines stays, and a concept the
    new documents only name again either joins the class that already holds it or is added
    beside it, depending on what the model says the two names mean.
    """
    schema = _read(schema_path)
    class_sources = _consolidate(candidates, "class")
    slot_sources = _consolidate(candidates, "relation")
    plan = _update_plan(llm, list(class_sources), list(slot_sources), config)
    duplicates = _duplicates(schema, class_sources, candidates, config, llm, log, embedder)
    _add_classes(schema, class_sources, slot_sources, duplicates, plan)
    _add_slots(schema, slot_sources, candidates, plan, config, llm, log)
    return _write(schema, schema_path)
