"""Telling a new concept apart from the one already in the ontology."""

import logging
import math
from typing import Protocol

from pydantic import BaseModel

from onto.config import BuilderConfig
from onto.llm import LLM, CompletionRequest

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1024

_INSTRUCTIONS = """You are an ontology engineer. Two class names describe concepts of an \
ontology, and it has to be decided whether they are two names for one concept.

Rules:
- Answer whether the two names denote the same concept, whatever wording each of them uses.
- Judge the concept, not the name: a narrower or a broader concept is not the same one.

Answer with a single JSON object and nothing else:
{"same_concept": true}"""


class Embedder(Protocol):
    """Maps concept names to vectors whose cosine similarity says how alike they are."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the order the texts were given."""
        ...


class EmbeddingError(Exception):
    """Raised when an embedding request fails — the unit a caller may retry."""


class _Verdict(BaseModel):
    same_concept: bool = False


def cosine(left: list[float], right: list[float]) -> float:
    """The cosine of the angle between two vectors, which ignores how long they are."""
    left_length = math.sqrt(sum(value**2 for value in left))
    right_length = math.sqrt(sum(value**2 for value in right))
    if left_length == 0 or right_length == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_length * right_length)


def closest_of(
    embedder: Embedder, existing: list[str], proposed: list[str], threshold: float
) -> dict[str, tuple[str, float]]:
    """For every proposed concept, the existing one it most resembles — but only when it
    resembles it closely enough for the model to be asked whether the two are one.

    A pair short of the threshold is left out: a concept unlike everything in the ontology is
    a new one, and asking the model about it would be a question with a single answer.
    """
    if not existing or not proposed:
        return {}
    vectors = embedder.embed([*existing, *proposed])
    first_proposed = len(existing)
    matches: dict[str, tuple[str, float]] = {}
    for offset, name in enumerate(proposed):
        score, other = max(
            (cosine(vectors[first_proposed + offset], vectors[index]), known)
            for index, known in enumerate(existing)
        )
        if score >= threshold:
            matches[name] = (other, score)
    return matches


def _prompt(existing: str, proposed: str) -> str:
    return "\n\n".join(
        [
            _INSTRUCTIONS,
            f"Class already in the ontology: {existing}",
            f"Class proposed by the new documents: {proposed}",
        ]
    )


def verify_merge(llm: LLM, config: BuilderConfig, existing: str, proposed: str) -> bool:
    """Ask the model whether a proposed concept is the one the ontology already has.

    Embeddings only say that two names lie close together; whether they name one concept is a
    question about what they mean. An answer that cannot be read is taken as "not the same",
    which keeps the concept as a class of its own: an unmergeable pair costs a redundant
    class, a wrongly merged one would swallow a concept the corpus distinguishes.
    """
    reply = llm.complete(
        CompletionRequest(
            model=config.model, prompt=_prompt(existing, proposed), max_tokens=_MAX_TOKENS
        )
    )
    try:
        return _Verdict.model_validate_json(reply).same_concept
    except ValueError as error:
        logger.error("merge verdict for %s/%s unreadable: %s", proposed, existing, error)
        return False
