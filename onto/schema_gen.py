import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from onto.config import BuilderConfig
from onto.dedup import Embedder, closest_of, verify_merge
from onto.extraction import Candidate, CandidateKind, pascal_name, snake_name
from onto.llm import LLM, CompletionRequest, read_json
from onto.provenance import ProvenanceLog, SourceRef

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096
SCHEMA_FILE_NAME = "schema.yaml"
SCHEMA_NAMESPACE = "https://example.org"

_MERGED = "class.merged"
_SLOT_CREATED = "slot.created"
_SLOT_UPDATED = "slot.updated"
_CREATED = "class.created"
_UPDATED = "class.updated"

# a relation is written as a slot, so it is the slot vocabulary the configuration constrains and
# the slot vocabulary a rejection is reported against
_REJECTION: dict[CandidateKind, tuple[str, str]] = {
    "class": ("class.rejected", "not_in_allowed_classes"),
    "relation": ("slot.rejected", "not_in_allowed_relations"),
}

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


_Readings = dict[tuple[CandidateKind, str], tuple[list[SourceRef], str]]


def _index(candidates: list[Candidate]) -> _Readings:
    """Where each proposed concept was read: every chunk it came from, and the text of one.

    A concept the corpus states in several chunks keeps all of them; the excerpt is the one of
    the first of them, because a single passage is all a log line can point at.
    """
    indexed: _Readings = {}
    for candidate in candidates:
        key = (candidate.kind, candidate.name)
        sources, excerpt = indexed.get(key, ([], candidate.source_excerpt))
        sources.extend(candidate.source_documents)
        indexed[key] = (sources, excerpt)
    return indexed


def _reading(readings: _Readings, kind: CandidateKind, name: str) -> tuple[list[SourceRef], str]:
    return readings.get((kind, name), ([], ""))


def _allowed(kind: CandidateKind, config: BuilderConfig) -> set[str] | None:
    """The concept names the configuration allows, or `None` when it names none.

    A configuration that states no allow-list scopes the build by domain alone and every
    concept the corpus states is admissible. One that states an allow-list is a boundary the
    prompt asks the model to respect and this module enforces, so the comparison runs on the
    names in the form they are written in: `vehicle` in the configuration admits the `Vehicle`
    the extractor normalises the model's wording to.
    """
    concepts = config.allowed_classes if kind == "class" else config.allowed_relations
    if not concepts:
        return None
    normalise = pascal_name if kind == "class" else snake_name
    return {normalise(name) for name in concepts}


def _admit(
    consolidated: dict[str, list[str]],
    kind: CandidateKind,
    config: BuilderConfig,
    readings: _Readings,
    log: ProvenanceLog,
) -> list[str]:
    """The proposed names the configuration allows, in the order the corpus stated them, and a
    record of the ones it does not.

    A prompt is a request rather than a boundary: a model that names a concept outside an
    allow-list would otherwise have it written into the schema as though the list had been
    honoured. Dropping it in silence is no better, because the ontology would then quietly
    differ from the configuration that describes it, so every rejection is logged with the
    chunk and the excerpt the concept was stated in.

    The order is the order of `consolidated` rather than that of a set: the same corpus must
    reach the model in the same order and write the same schema, or a build is not repeatable
    even with the model answering the same thing.
    """
    allowed = _allowed(kind, config)
    admitted: list[str] = []
    for name in consolidated:
        if allowed is None or name in allowed:
            admitted.append(name)
            continue
        event, reason = _REJECTION[kind]
        sources, excerpt = _reading(readings, kind, name)
        log.record(
            event=event, id=name, source_documents=sources, source_excerpt=excerpt, reason=reason
        )
    return admitted


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
    return _Plan.model_validate_json(read_json(reply))


def _classes(
    consolidated: dict[str, list[str]],
    known_slots: list[str],
    plan: _Plan,
    admitted: list[str],
    readings: _Readings,
    log: ProvenanceLog,
) -> dict[str, _ClassDefinition]:
    """A class the model left out of its plan, or one the configuration does not allow, is not
    part of the schema. Every class that is written is recorded as created, so the log is a
    record of the ontology that was built and not only of what an update changed."""
    permitted = set(admitted)
    written_slots = set(known_slots)
    definitions = {}
    for name, chunk_ids in consolidated.items():
        planned = plan.classes.get(name)
        if planned is None or name not in permitted:
            continue
        definitions[name] = _ClassDefinition(
            name=name,
            description=planned.description,
            slots=[slot for slot in planned.slots if slot in written_slots],
            annotations=_provenance(chunk_ids),
        )
        sources, excerpt = _reading(readings, "class", name)
        log.record(event=_CREATED, id=name, source_documents=sources, source_excerpt=excerpt)
    return definitions


def generate_tbox(
    candidates: list[Candidate],
    config: BuilderConfig,
    llm: LLM,
    output_dir: Path,
    log: ProvenanceLog,
) -> Path:
    """Write the T-Box of the extracted candidates as a LinkML schema.

    Every candidate that proposed the same name is consolidated into a single definition
    whose `source_documents` annotation lists the chunks it was read from. The schema is
    named after the output directory, so writing into `ontology/` yields `ontology-schema`.
    """
    class_sources = _consolidate(candidates, "class")
    slot_sources = _consolidate(candidates, "relation")
    readings = _index(candidates)
    admitted = _admit(class_sources, "class", config, readings, log)
    admitted_slots = _admit(slot_sources, "relation", config, readings, log)
    plan = _plan(llm, admitted, admitted_slots, config)
    name = f"{output_dir.name}-schema"
    schema = _Schema(
        id=f"{SCHEMA_NAMESPACE}/{name}",
        name=name,
        prefixes={output_dir.name: f"{SCHEMA_NAMESPACE}/{output_dir.name}/"},
        default_prefix=output_dir.name,
        default_range="string",
        imports=["linkml:types"],
        classes=_classes(class_sources, admitted_slots, plan, admitted, readings, log),
        slots={},
    )
    for slot in admitted_slots:
        schema.slots[slot] = _SlotDefinition(
            name=slot, annotations=_provenance(slot_sources[slot])
        )
        sources, excerpt = _reading(readings, "relation", slot)
        log.record(
            event=_SLOT_CREATED, id=slot, source_documents=sources, source_excerpt=excerpt
        )
    return _write(schema, output_dir / SCHEMA_FILE_NAME)


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
    return _UpdatePlan.model_validate_json(read_json(reply))


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
    return _Resolution.model_validate_json(read_json(reply)).range


def _duplicates(
    schema: _Schema,
    class_sources: dict[str, list[str]],
    admitted: list[str],
    readings: _Readings,
    config: BuilderConfig,
    llm: LLM,
    log: ProvenanceLog,
    embedder: Embedder,
) -> set[str]:
    """The proposed classes that turned out to name a concept the schema already has.

    The class already in the ontology survives and cites the chunks the merged name was read
    from, so the schema keeps saying where the concept was stated. The merged name is never
    written: it is a second word for one concept, and a class stands for a concept. Only
    classes the configuration allows are put to the model, because a question about a concept
    that will not be written has no use.

    A name the schema already holds is not compared with the schema either: it is that concept,
    and a vector of it sits at cosine 1.0 from itself, so the model would confirm a merge into
    itself and the class would be swallowed instead of cited.
    """
    pairs = closest_of(
        embedder,
        list(schema.classes),
        [name for name in admitted if name not in schema.classes],
        config.similarity_threshold,
    )
    duplicates = set()
    for name, (existing, _) in pairs.items():
        if not verify_merge(llm, config, existing, name):
            continue
        sources, excerpt = _reading(readings, "class", name)
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
    admitted: list[str],
    admitted_slots: list[str],
    readings: _Readings,
    duplicates: set[str],
    plan: _UpdatePlan,
    log: ProvenanceLog,
) -> None:
    """The classes the model left out of its plan are not added, and neither are the ones
    merged into a class already there or refused by the configuration. A class the corpus names
    again keeps the description it has and cites the new chunk beside the old ones: a class is
    one concept, and a later document does not get to decide what it means. A `is_a` naming a
    class the schema will not have is dropped, because a superclass that is not there describes
    nothing. Both outcomes are logged, so the log says what the schema ended up holding."""
    known_slots = {*schema.slots, *admitted_slots}
    permitted = set(admitted)
    known_classes = ({*schema.classes, *permitted}) - duplicates
    for name, chunk_ids in class_sources.items():
        planned = plan.classes.get(name)
        if name in duplicates or planned is None or name not in permitted:
            continue
        sources, excerpt = _reading(readings, "class", name)
        if name in schema.classes:
            _cite(schema.classes[name].annotations, chunk_ids)
            log.record(event=_UPDATED, id=name, source_documents=sources, source_excerpt=excerpt)
            continue
        schema.classes[name] = _ClassDefinition(
            name=name,
            description=planned.description,
            slots=[slot for slot in planned.slots if slot in known_slots],
            is_a=planned.is_a if planned.is_a in known_classes else None,
            annotations=_provenance(chunk_ids),
        )
        log.record(event=_CREATED, id=name, source_documents=sources, source_excerpt=excerpt)


def _add_slots(
    schema: _Schema,
    slot_sources: dict[str, list[str]],
    admitted: list[str],
    readings: _Readings,
    plan: _UpdatePlan,
    config: BuilderConfig,
    llm: LLM,
    log: ProvenanceLog,
) -> None:
    """A slot the new documents repeat is left as it is, except that it cites them too; a slot
    they give another type is put to the model, and the type it keeps is the one written."""
    for name in admitted:
        chunk_ids = slot_sources[name]
        proposed = plan.slot_ranges.get(name)
        known = schema.slots.get(name)
        if known is None:
            schema.slots[name] = _SlotDefinition(
                name=name, range=proposed, annotations=_provenance(chunk_ids)
            )
            sources, excerpt = _reading(readings, "relation", name)
            log.record(
                event=_SLOT_CREATED, id=name, source_documents=sources, source_excerpt=excerpt
            )
            continue
        _cite(known.annotations, chunk_ids)
        if proposed is None or known.range is None or proposed == known.range:
            continue
        known.range = _resolve_range(llm, config, name, known.range, proposed)
        sources, excerpt = _reading(readings, "relation", name)
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
    readings = _index(candidates)
    admitted = _admit(class_sources, "class", config, readings, log)
    admitted_slots = _admit(slot_sources, "relation", config, readings, log)
    plan = _update_plan(llm, admitted, admitted_slots, config)
    duplicates = _duplicates(schema, class_sources, admitted, readings, config, llm, log, embedder)
    _add_classes(
        schema, class_sources, admitted, admitted_slots, readings, duplicates, plan, log
    )
    _add_slots(schema, slot_sources, admitted_slots, readings, plan, config, llm, log)
    return _write(schema, schema_path)
