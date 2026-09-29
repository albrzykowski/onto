"""Helpers shared by step-definition modules."""

import json
import re
from collections.abc import Callable
from pathlib import Path

from onto.llm import CompletionRequest


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
