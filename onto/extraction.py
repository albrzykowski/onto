import logging
import re
from collections.abc import Callable, Iterator
from typing import Literal

from pydantic import BaseModel, Field

from onto.chunking import Chunk
from onto.config import BuilderConfig
from onto.llm import LLM, CompletionRequest, read_json
from onto.provenance import SourceRef

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096

CandidateKind = Literal["class", "relation"]

_INSTRUCTIONS = """You are an ontology engineer. Read the source text and name the concepts it \
states, together with the relations between them, that a domain expert would call \
significant.

Rules:
- Write every name in English, even when the source text is written in another language.
- A class name is PascalCase; a relation name is snake_case.
- Copy the excerpt verbatim from the source text; it is the only proof of where a \
concept came from.
- Skip what the text merely assumes, mentions in passing, or is about outside the domain.

Answer with a single JSON object and nothing else:
{"classes": [{"name": ..., "excerpt": ...}], "relations": [{"name": ..., "excerpt": ...}]}"""


def _output_contract(config: BuilderConfig) -> str:
    """The rules that decide whether the reply can be read at all.

    A model left to its own devices enumerates every noun it finds and runs out of tokens
    mid-object, and a reply that stops halfway cannot be repaired by any amount of parsing.
    Measured on `mistral-medium-3-5`: without the cap a batch of dense prose produced
    14 700 characters and never closed, with the cap 1 200. So the cap is what makes the
    answer readable; the rest only keeps it free of decoration.
    """
    limit = config.max_concepts_per_batch
    return "\n".join(
        [
            "Output contract, which is not negotiable:",
            f"- At most {limit} classes and at most {limit} relations. Choose the most"
            " significant; a shorter list is better than a longer one. Stop and close the"
            " object once you reach the limit.",
            '- Your entire reply is one JSON object: the first character is "{" and the last'
            ' is "}". No prose before it, no prose after it.',
            "- Do not wrap the object in a markdown code fence.",
        ]
    )

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NON_WORD = re.compile(r"[^A-Za-z0-9]+")


class Candidate(BaseModel):
    """A concept the LLM proposed from a chunk, before it is accepted into the ontology."""

    kind: CandidateKind
    name: str
    source_documents: list[SourceRef] = Field(default_factory=list)
    source_excerpt: str = ""


class _Proposal(BaseModel):
    name: str
    excerpt: str = ""


class _Answer(BaseModel):
    classes: list[_Proposal] = Field(default_factory=list)
    relations: list[_Proposal] = Field(default_factory=list)


def _words(name: str) -> list[str]:
    return [word for word in _NON_WORD.split(_CAMEL_BOUNDARY.sub(" ", name)) if word]


def _pascal_case(name: str) -> str:
    return "".join(word.capitalize() for word in _words(name))


def _snake_case(name: str) -> str:
    return "_".join(word.lower() for word in _words(name))


def _described_lines(concepts: dict[str, str]) -> list[str]:
    """The concepts as the prompt states them: a name, then what it means.

    A bare list of names leaves the model to work out what each one covers, and a name it
    has never seen is one it is most likely to replace with its own wording.
    """
    return [f"- {name}: {description}" for name, description in concepts.items()]


def _scope(config: BuilderConfig) -> str:
    """The section that narrows the set of concepts the LLM may propose.

    With an allow-list the model may only use the concepts it is given; with domains alone
    it is scoped to the domain but may still name what it finds, which is the whole point
    of extracting an ontology rather than transcribing a list.
    """
    constraints = ["Domains:", *_described_lines(config.domains)]
    if config.allowed_classes or config.allowed_relations:
        constraints += [
            "Predefined classes:",
            *_described_lines(config.allowed_classes),
            "Predefined relations:",
            *_described_lines(config.allowed_relations),
            "Use only these concepts and nothing else; do not propose anything outside this list.",
        ]
    else:
        constraints.append(
            "Extract the concepts that are relevant to the domains above, and nothing else."
        )
    return "\n".join(["Scope of the ontology:", *constraints])


def _prompt(batch: list[Chunk], config: BuilderConfig) -> str:
    sections = [_INSTRUCTIONS, _scope(config), _output_contract(config), "Source text:"]
    sections.extend(f"[{chunk.chunk_id}]\n{chunk.text}" for chunk in batch)
    return "\n\n".join(section for section in sections if section)


def _ask(llm: LLM, batch: list[Chunk], config: BuilderConfig) -> str:
    return llm.complete(
        CompletionRequest(
            model=config.model, prompt=_prompt(batch, config), max_tokens=_MAX_TOKENS
        )
    )


def _candidates_of(
    kind: CandidateKind,
    proposals: list[_Proposal],
    sources: list[SourceRef],
    to_name: Callable[[str], str],
) -> list[Candidate]:
    return [
        Candidate(
            kind=kind,
            name=to_name(proposal.name),
            source_documents=sources,
            source_excerpt=proposal.excerpt,
        )
        for proposal in proposals
    ]


def _batches(chunks: list[Chunk], size: int) -> Iterator[list[Chunk]]:
    for start in range(0, len(chunks), size):
        yield chunks[start : start + size]


def extract(chunks: list[Chunk], config: BuilderConfig, llm: LLM) -> list[Candidate]:
    """Ask the LLM which concepts each batch of chunks states.

    Chunks are sent in batches of `config.batch_size`. An `LLMError` from the model is
    logged and the batch skipped, so one bad chunk never aborts the build — the catch is
    deliberately wider, because an adapter that lets a provider's own exception escape
    would otherwise take the whole build down. A candidate cites every chunk of the batch
    it was read from, because the model saw all of them at once; its `source_excerpt` is
    what pins down the exact text the candidate came from.
    """
    candidates: list[Candidate] = []
    for batch in _batches(chunks, config.batch_size):
        try:
            answer = _Answer.model_validate_json(read_json(_ask(llm, batch, config)))
        except Exception as error:
            logger.error(
                "extraction failed for %s: %s", [chunk.chunk_id for chunk in batch], error
            )
            continue
        sources = [SourceRef(path=chunk.source_path, chunk_id=chunk.chunk_id) for chunk in batch]
        candidates.extend(_candidates_of("class", answer.classes, sources, _pascal_case))
        candidates.extend(_candidates_of("relation", answer.relations, sources, _snake_case))
    return candidates
