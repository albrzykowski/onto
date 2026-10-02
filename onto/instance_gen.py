import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from onto.chunking import Chunk
from onto.config import BuilderConfig
from onto.extraction import described_by_chunk, merge_descriptions
from onto.llm import LLM, CompletionRequest, read_json
from onto.provenance import ProvenanceLog, SourceRef

logger = logging.getLogger(__name__)

INSTANCES_FILE_NAME = "instances.yaml"

_MAX_TOKENS = 4096
_CREATED = "instance.created"
_UPDATED = "instance.updated"
_REJECTED = "instance.rejected"
_NOT_IN_TBOX = "not_in_tbox"
_IDENTIFIER_TAKEN = "identifier_taken"
_UNRESOLVED = "unresolved_reference"

_INSTRUCTIONS = """You are an ontology engineer. Read the source text and name the concrete \
entities it states, as instances of the classes listed below.

Rules:
- Name every entity the text states concretely, and skip what it merely mentions in passing.
- Give each slot the name of the entity it points to, written exactly as the text writes it.
- Use only the classes and slots listed below; invent nothing.
- Every slot value is a single string naming the one entity it points to. A slot is never a \
list, even when the text names several things for it; keep the most significant one.
- State in one sentence, in English, what this text says the entity is.
- Copy the excerpt verbatim from the source text; it is the only proof of where the \
instance came from.

Answer with a single JSON object and nothing else. Every value is a string in double quotes,
and every class and slot name is one of those listed above — never copied from the example
below, which only shows the shape:
{"instances": [{"name": "Engine No 1", "class": "Engine", "slots": {"part_of": "Chassis"},
"description": "The first engine the text describes.",
"excerpt": "Engine No 1 was the first engine the text describes."}]}"""


def _output_contract(config: BuilderConfig) -> str:
    """The rules that decide whether the reply can be read at all; see `onto.extraction`
    for why a model asked for JSON will otherwise enumerate until it runs out of tokens."""
    limit = config.max_concepts_per_batch
    return "\n".join(
        [
            "Output contract, which is not negotiable:",
            f"- At most {limit} instances. Choose the most significant; a shorter list is"
            " better than a longer one. Stop and close the object once you reach the limit.",
            '- Your entire reply is one JSON object: the first character is "{" and the last'
            ' is "}". No prose before it, no prose after it.',
            "- Do not wrap the object in a markdown code fence.",
        ]
    )


class Instance(BaseModel):
    """A concrete fact stated by the corpus: an entity of one of the T-Box classes.

    `name` is the wording the model used and `id` is the token it is written under. Both are
    kept because two different wordings can reduce to one token, and an ontology that dropped
    one of them silently would be indistinguishable from one that simply did not find it.
    """

    id: str
    name: str
    class_name: str
    description: str = ""
    slot_values: dict[str, str] = Field(default_factory=dict)
    source_documents: list[SourceRef] = Field(default_factory=list)
    source_excerpt: str = ""


class _Proposal(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    class_name: str = Field(alias="class")
    slots: dict[str, str] = Field(default_factory=dict)
    excerpt: str = ""
    description: str = ""


class _Answer(BaseModel):
    instances: list[_Proposal] = Field(default_factory=list)


def _identifier(name: str) -> str:
    """An instance, and every value pointing at one, is written as a single token of word
    characters. The model spells identifiers in prose, so `1.6 TDI` and `VW Golf` have to
    name the same instance in the A-Box, in a slot value and in the log."""
    return "_".join(re.findall(r"\w+", name))


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


def _prompt(classes: dict[str, list[str]], chunk: Chunk, config: BuilderConfig) -> str:
    sections = [
        _INSTRUCTIONS,
        f"Classes of the schema:\n{_listing(classes)}",
        _output_contract(config),
        f"Source text:\n[{chunk.chunk_id}]\n{chunk.text}",
    ]
    return "\n\n".join(sections)


def _proposals(
    llm: LLM, config: BuilderConfig, classes: dict[str, list[str]], chunk: Chunk
) -> list[_Proposal]:
    reply = llm.complete(
        CompletionRequest(
            model=config.model, prompt=_prompt(classes, chunk, config), max_tokens=_MAX_TOKENS
        )
    )
    return _Answer.model_validate_json(read_json(reply)).instances


def _instance(proposal: _Proposal, slots: list[str], chunk: Chunk) -> Instance:
    return Instance(
        id=_identifier(proposal.name),
        name=proposal.name,
        class_name=proposal.class_name,
        description=proposal.description,
        slot_values={
            slot: _identifier(value) for slot, value in proposal.slots.items() if slot in slots
        },
        source_documents=[chunk.source_ref()],
        source_excerpt=proposal.excerpt,
    )


def _entry(instance: Instance, unresolved: dict[str, str]) -> dict[str, Any]:
    """One instance as written: its class, its description, the slot values stated for it,
    and its provenance. The description is written only when the corpus stated one."""
    return {
        "class": instance.class_name,
        **({"description": instance.description} if instance.description else {}),
        **{
            slot: value
            for slot, value in instance.slot_values.items()
            if slot not in unresolved
        },
        "annotations": {
            "source_documents": {
                "tag": "source_documents",
                "value": [source.chunk_id for source in instance.source_documents],
            },
        },
    }


def _cite_entry(entry: dict[str, Any], instance: Instance) -> None:
    """Add the chunks a later document states the entity in to what the entry already cites."""
    cited = entry["annotations"]["source_documents"]["value"]
    for source in instance.source_documents:
        if source.chunk_id not in cited:
            cited.append(source.chunk_id)


def _cite(instance: Instance, other: Instance) -> None:
    """Every chunk the same entity was stated in is remembered, so the ontology keeps saying
    where the fact came from however many documents agree on it."""
    cited = [source.chunk_id for source in instance.source_documents]
    instance.source_documents.extend(
        source
        for source in other.source_documents
        if source.chunk_id not in cited
    )


def _instances_of(
    chunks: list[Chunk],
    config: BuilderConfig,
    llm: LLM,
    classes: dict[str, list[str]],
    log: ProvenanceLog,
) -> dict[str, Instance]:
    """What the chunks state, as instances of the classes the T-Box defines.

    An entity the corpus names in several chunks becomes one instance citing all of them. Two
    entities whose names reduce to the same token are a different matter: only one can stand
    under that id, so the one already there is kept and the other is refused and logged rather
    than silently overwriting it. The log says the id and quotes the text the refused entity
    was read from, which is where its name is to be found.

    An entity the chunks describe differently gets one description reconciled from all of them,
    and the reconciliation is recorded: the instance is written with that wording, so the log
    has to say which wording that was.
    """
    instances: dict[str, Instance] = {}
    stated: list[tuple[str, str]] = []
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
                    source_documents=[chunk.source_ref()],
                    reason=_NOT_IN_TBOX,
                )
                continue
            instance = _instance(proposal, classes[proposal.class_name], chunk)
            known = instances.get(instance.id)
            if known is not None and known.name != instance.name:
                logger.warning(
                    "%s and %s both name the instance %s; keeping the first",
                    known.name,
                    instance.name,
                    instance.id,
                )
                log.record(
                    event=_REJECTED,
                    id=instance.id,
                    source_excerpt=instance.source_excerpt,
                    source_documents=instance.source_documents,
                    reason=_IDENTIFIER_TAKEN,
                )
                continue
            if known is None:
                instances[instance.id] = instance
            else:
                _cite(known, instance)
            stated.append((instance.id, proposal.description))
    for id_, description in merge_descriptions(
        llm, config, "instance", described_by_chunk(stated)
    ).items():
        instance = instances[id_]
        instance.description = description
        log.record(
            event=_UPDATED,
            id=id_,
            source_documents=instance.source_documents,
            source_excerpt=instance.source_excerpt,
            description=description,
        )
    return instances


def _merge(entries: dict[str, Any], instances: dict[str, Instance], log: ProvenanceLog) -> None:
    """Write the instances into the entries already on disk, one event per instance written.

    An instance already there is not restated by a later document that names the same entity
    with less of it: the earlier entry stands and cites the new chunk, which is how a class
    the corpus names twice is treated in the T-Box.

    A slot value has to be resolved once every instance is known, because the chunk that
    states it may well not be the chunk that writes the entity it points at. A value that
    names nothing in the A-Box is left out and recorded: a slot filled with a dangling name
    states a fact the ontology cannot stand behind, and inventing the missing instance is a
    larger change than the corpus made.
    """
    written = set(entries) | set(instances)
    for instance in instances.values():
        unresolved = {
            slot: value for slot, value in instance.slot_values.items() if value not in written
        }
        for value in unresolved.values():
            log.record(
                event=_REJECTED,
                id=instance.id,
                source_documents=instance.source_documents,
                source_excerpt=instance.source_excerpt,
                value=value,
                reason=_UNRESOLVED,
            )
        entry = entries.get(instance.id)
        if entry is None:
            entries[instance.id] = _entry(instance, unresolved)
            event = _CREATED
        else:
            _cite_entry(entry, instance)
            event = _UPDATED
        log.record(
            event=event,
            id=instance.id,
            source_documents=instance.source_documents,
            source_excerpt=instance.source_excerpt,
        )


def _write(entries: dict[str, Any], path: Path) -> Path:
    path.write_text(
        yaml.safe_dump({"instances": entries}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("wrote %s with %s instances", path, len(entries))
    return path


def _read(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    return document.get("instances", {}) if document else {}


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
    Every written instance is recorded in the log and carries the chunk and the excerpt it was
    read from. Each chunk is one request; a failure is logged and the chunk skipped, so one bad
    chunk never aborts the build — the catch is deliberately wider, because an adapter that lets
    a provider's own exception escape would otherwise take the whole build down.
    """
    entries: dict[str, Any] = {}
    _merge(entries, _instances_of(chunks, config, llm, _classes_of(schema_path), log), log)
    return _write(entries, schema_path.parent / INSTANCES_FILE_NAME)


def extend_instances(
    chunks: list[Chunk],
    config: BuilderConfig,
    llm: LLM,
    schema_path: Path,
    log: ProvenanceLog,
) -> Path:
    """Add to `instances.yaml` the instances the new chunks state, and leave every entry
    already written as it is.

    An update adds what the corpus has newly stated; it does not restate what an earlier
    build already established, so an instance accepted once is not overwritten by a later
    document that names the same entity with less of it. Naming that entity again is not
    nothing, though, so the entry cites the document that named it.
    """
    path = schema_path.parent / INSTANCES_FILE_NAME
    entries = _read(path)
    _merge(entries, _instances_of(chunks, config, llm, _classes_of(schema_path), log), log)
    return _write(entries, path)
