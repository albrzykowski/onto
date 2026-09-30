"""Helpers shared by step-definition modules."""

import json
import re
from collections.abc import Callable
from pathlib import Path

from onto.config import BuilderConfig
from onto.llm import CompletionRequest

# A configuration that loads. Every field is required, so a step that only cares about one
# of them still has to state the rest; this is that state, written once.
VALID_CONFIG = {
    "domains": {"automotive": "Passenger and commercial vehicles and their components"},
    "allowed_classes": {},
    "allowed_relations": {},
    "mode": "override",
    "model": "mistral/mistral-large-latest",
    "embedding_model": "mistral/mistral-embed",
    "api_key": "sk-test-key",
    "embedding_api_key": "sk-test-embed-key",
    "chunking_strategy": "fixed",
    "max_chunk_tokens": 2000,
    "overlap_tokens": 200,
    "batch_size": 1,
    "max_concepts_per_batch": 5,
    "similarity_threshold": 0.85,
}


def valid_config(**overrides: object) -> BuilderConfig:
    """A loadable configuration, with the fields the caller is about to change replaced.

    Built through `model_validate` rather than keyword arguments: the merged mapping holds
    values of several types, and the keywords would be checked against one field's type.
    """
    return BuilderConfig.model_validate({**VALID_CONFIG, **overrides})


def described(raw: str) -> dict[str, str]:
    """A Gherkin list of described concepts is written `A as "one", B as "two"`."""
    concepts = {}
    for name, description in re.findall(r'([\w]+)\s+as\s+"([^"]+)"', raw):
        concepts[name] = description
    return concepts


def quoted(group: str) -> str:
    """A Gherkin parser matching a double-quoted value into a named group."""
    return rf'"(?P<{group}>[^"]+)"'


def word(group: str) -> str:
    """A Gherkin parser matching a bare word into a named group."""
    return rf"(?P<{group}>\w+)"


def split_names(raw: str) -> list[str]:
    """A Gherkin list of names is written with commas and conjunctions: `A, B and C`."""
    return [name.strip() for name in re.split(r",|\band\b", raw) if name.strip()]


def log_lines(provenance_path: Path) -> list[str]:
    text = provenance_path.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def log_events(provenance_path: Path) -> list[dict]:
    """Every event of a provenance log, in the order it was written."""
    return [json.loads(line) for line in log_lines(provenance_path)]


def event_names(provenance_path: Path) -> list[str]:
    return [event["event"] for event in log_events(provenance_path)]


class FakeLLM:
    """Stands in for a language model; the features speak of the LLM, not of a provider."""

    def __init__(self, respond: Callable[[int], str]) -> None:
        self._respond = respond
        self.prompts: list[str] = []

    def complete(self, request: CompletionRequest) -> str:
        self.prompts.append(request.prompt)
        return self._respond(len(self.prompts) - 1)
