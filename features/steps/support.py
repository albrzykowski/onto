"""Helpers shared by step-definition modules, and the one step two features share.

An update is a whole build, so it is run through `onto.builder.build` rather than through the
generators. That step definition therefore lives here rather than in either feature's own
module: `update-mode.feature` and `abox-generation.feature` both run an update, and two
definitions of one step text would leave pytest-bdd to pick a winner.
"""

import json
import logging
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import when

from onto import builder
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


def merged_description(concept: str, texts: list[str]) -> str:
    """What the model answers when asked to reconcile several readings of one concept.

    A wording of its own, so an entry or a schema that kept one of the readings instead of
    the reconciliation would be visible in the output.
    """
    return f"{concept} as all {len(texts)} chunks together describe it."


def log_lines(provenance_path: Path) -> list[str]:
    text = provenance_path.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def log_events(provenance_path: Path) -> list[dict]:
    """Every event of a provenance log, in the order it was written."""
    return [json.loads(line) for line in log_lines(provenance_path)]


def event_names(provenance_path: Path) -> list[str]:
    return [event["event"] for event in log_events(provenance_path)]


def event_named(provenance_path: Path, event: str) -> dict:
    """The one event of that kind, so a scenario can read the fields it was written with."""
    events = log_events(provenance_path) if provenance_path.exists() else []
    assert event in [entry["event"] for entry in events], [entry["event"] for entry in events]
    return next(entry for entry in events if entry["event"] == event)


def error_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The errors a run logged, because the scenarios read the failure rather than a raise."""
    return [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]


def config_for(state: dict) -> BuilderConfig:
    """The configuration a scenario built up, so a step does not have to seed it first."""
    if state["config"] is None:
        state["config"] = valid_config()
    return state["config"]


class FakeLLM:
    """Stands in for a language model; the features speak of the LLM, not of a provider."""

    def __init__(self, respond: Callable[[int], str]) -> None:
        self._respond = respond
        self.prompts: list[str] = []

    def complete(self, request: CompletionRequest) -> str:
        self.prompts.append(request.prompt)
        return self._respond(len(self.prompts) - 1)


# The ontology and the corpus an update starts from. Both features that run an update need
# them, and the seeds are what tell a step how far the previous build got.

CORPUS = "corpus"
EXCERPT = "The Golf has a combustion engine and the Passat a manual transmission."

EXISTING_CLASS = "Vehicle"
EXISTING_INSTANCE = "VW_Golf"
EXISTING_RANGE = "string"
PROPOSED_RANGE = "integer"

ONTOLOGY_FILES = ("schema.yaml", "instances.yaml")
MERGE_MARKER = "denote the same concept"


def input_dir(workdir: Path) -> Path:
    return workdir / CORPUS


def chunk_id(name: str) -> str:
    """The id `chunk_document` gives the first chunk of a document of this corpus."""
    return f"{CORPUS}/{name}#c1"


def write_document(workdir: Path, name: str, text: str) -> None:
    corpus = input_dir(workdir)
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / name).write_text(text, encoding="utf-8")


def write_yaml(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def ontology_as_written(output_dir: Path) -> dict[str, str]:
    """The T-Box and the A-Box as they stand, to tell a rewrite from an extension."""
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(output_dir.iterdir())
        if path.name in ONTOLOGY_FILES
    }


def source_document_annotation(values: list[str]) -> dict[str, Any]:
    return {"tag": "source_documents", "value": values}


def existing_schema() -> dict[str, Any]:
    cited = [chunk_id("old.txt")]
    return {
        "id": "https://example.org/ontology-schema",
        "name": "ontology-schema",
        "prefixes": {"ontology": "https://example.org/ontology/"},
        "default_prefix": "ontology",
        "default_range": EXISTING_RANGE,
        "imports": ["linkml:types"],
        "classes": {
            EXISTING_CLASS: {
                "name": EXISTING_CLASS,
                "description": "A compact passenger car produced since 1974.",
                "slots": ["has_engine"],
                "annotations": {"source_documents": source_document_annotation(cited)},
            }
        },
        "slots": {
            "has_engine": {
                "name": "has_engine",
                "annotations": {"source_documents": source_document_annotation(cited)},
            }
        },
    }


def existing_instances() -> dict[str, Any]:
    return {
        "instances": {
            EXISTING_INSTANCE: {
                "class": EXISTING_CLASS,
                "has_engine": "1_6_TDI",
                "annotations": {
                    "source_documents": source_document_annotation([chunk_id("old.txt")]),
                },
            }
        }
    }


class FakeEmbedder:
    """Vectors that reproduce the similarity a scenario states, and nothing else.

    Every text is given an axis of its own, so two texts given no resemblance are orthogonal;
    a text that should resemble another leans its vector onto the axis of that other one.
    """

    def __init__(self, resemblances: dict[str, tuple[str, float]]) -> None:
        self._resemblances = resemblances

    def embed(self, texts: list[str]) -> list[list[float]]:
        axis = {text: index for index, text in enumerate(texts)}
        vectors = [[0.0] * len(texts) for _ in texts]
        for index in range(len(texts)):
            vectors[index][index] = 1.0
        for text, (other, score) in self._resemblances.items():
            if text not in axis or other not in axis:
                continue
            vectors[axis[text]] = [0.0] * len(texts)
            vectors[axis[text]][axis[text]] = math.sqrt(max(0.0, 1 - score**2))
            vectors[axis[text]][axis[other]] = score
        return vectors


def update_client(state: dict) -> FakeLLM:
    """An update asks the model five different things; the double answers each by what the
    prompt asks for, so no scenario depends on the order the calls happen to come in.
    """

    def concepts() -> str:
        return json.dumps(
            {
                "classes": [
                    {"name": name, "excerpt": EXCERPT} for name in state["class_names"]
                ],
                "relations": [
                    {"name": name, "excerpt": EXCERPT} for name in state.get("relations", [])
                ],
            }
        )

    def plan() -> str:
        return json.dumps(
            {
                "classes": {
                    name: {
                        "description": f"A {name} as the model described it.",
                        "slots": state.get("planned_slots", []),
                        **({"is_a": state["parent"]} if state.get("parent") else {}),
                    }
                    for name in state["planned_classes"]
                },
                "slot_ranges": state.get("slot_ranges", {}),
            }
        )

    def instances() -> str:
        return json.dumps(
            {
                "instances": [
                    {
                        "name": state["instance_name"],
                        "class": state["instances_class"],
                        "slots": {},
                        "excerpt": EXCERPT,
                    }
                ]
            }
        )

    def respond(call: int) -> str:
        prompt = client.prompts[call]
        if MERGE_MARKER in prompt:
            return json.dumps({"same_concept": state.get("merge_verified", False)})
        if "Candidate classes:" in prompt or "New concepts:" in prompt:
            return plan()
        if "already in use" in prompt:
            return json.dumps({"range": state.get("resolved_range", PROPOSED_RANGE)})
        if "Classes of the schema:" in prompt:
            return instances()
        return concepts()

    client = FakeLLM(respond)
    return client


@when("update mode runs")
def step_when_update_mode_runs(state: dict, workdir: Path, output_dir: Path) -> None:
    state.setdefault("class_names", [])
    state.setdefault("planned_classes", state["class_names"])
    state.setdefault("instances_class", EXISTING_CLASS)
    state.setdefault("instance_name", "VW Passat")
    state["before"] = ontology_as_written(output_dir)
    state["client"] = update_client(state)
    builder.build(
        input_dir(workdir),
        output_dir,
        valid_config(mode="update"),
        state["client"],
        FakeEmbedder(state.get("resemblances", {})),
    )
