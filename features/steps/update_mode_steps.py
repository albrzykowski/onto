import json
import math
from pathlib import Path

import yaml
from pytest_bdd import given, parsers, then, when

from features.steps.support import FakeLLM, log_events, quoted, split_names, word
from onto.builder import STATE_FILE_NAME, build
from onto.config import BuilderConfig
from onto.ingestion import compute_fingerprint

CORPUS = "corpus"
OLD_TEXT = "VW has been producing the Golf, a compact passenger car, since 1974."
NEW_TEXT = "The Passat has a six-speed manual transmission."
EXCERPT = "The Golf has a combustion engine and the Passat a manual transmission."
NEW_DOCUMENT = "new.txt"

EXISTING_CLASS = "Vehicle"
EXISTING_INSTANCE = "VW_Golf"
WEIGHT_SLOT = "weight"
EXISTING_RANGE = "string"
PROPOSED_RANGE = "integer"
RESOLVED_RANGE = "string"

ONTOLOGY_FILES = ("schema.yaml", "instances.yaml")
MERGE_MARKER = "denote the same concept"


def input_dir(workdir: Path) -> Path:
    return workdir / CORPUS


def chunk_id(workdir: Path, name: str) -> str:
    """The id `chunk_document` gives the first chunk of a document of this corpus."""
    return f"{input_dir(workdir) / name}#c1"


def write_document(workdir: Path, name: str, text: str) -> None:
    corpus = input_dir(workdir)
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / name).write_text(text, encoding="utf-8")


def write_yaml(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_json(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ontology_as_written(output_dir: Path) -> dict[str, str]:
    """The T-Box and the A-Box as they stand, to tell a rewrite from an extension."""
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(output_dir.iterdir())
        if path.name in ONTOLOGY_FILES
    }


def cited_chunks(schema_path: Path, klass: str) -> list[str]:
    return read_yaml(schema_path)["classes"][klass]["annotations"]["source_documents"]["value"]


def event_named(provenance_path: Path, event: str) -> dict:
    events = log_events(provenance_path) if provenance_path.exists() else []
    assert event in [entry["event"] for entry in events], [entry["event"] for entry in events]
    return next(entry for entry in events if entry["event"] == event)


def provenance_mentioning(state: dict, first: str, second: str) -> list[str]:
    return [
        prompt
        for prompt in state["client"].prompts
        if MERGE_MARKER in prompt and first in prompt and second in prompt
    ]


def source_document_annotation(values: list[str]) -> dict:
    return {"tag": "source_documents", "value": values}


def existing_schema(workdir: Path) -> dict:
    cited = [chunk_id(workdir, "old.txt")]
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


def existing_instances(workdir: Path) -> dict:
    return {
        "instances": {
            EXISTING_INSTANCE: {
                "class": EXISTING_CLASS,
                "has_engine": "1_6_TDI",
                "annotations": {
                    "source_documents": source_document_annotation([chunk_id(workdir, "old.txt")]),
                    "source_excerpt": {
                        "tag": "source_excerpt",
                        "value": "The Golf has a 1.6 TDI engine.",
                    },
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


def client_for(state: dict) -> FakeLLM:
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
                        "name": "VW Passat",
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


# Background: the ontology an earlier build wrote

@given(parsers.re(rf'an existing ontology with a schema containing the class {word("klass")}$'))
def step_given_existing_ontology(state: dict, workdir: Path, schema_path: Path) -> None:
    state["schema_path"] = schema_path
    write_yaml(schema_path, existing_schema(workdir))


@given(parsers.re(rf'the instance {quoted("name")}'))
def step_given_existing_instance(workdir: Path, output_dir: Path) -> None:
    write_yaml(output_dir / "instances.yaml", existing_instances(workdir))


@given(parsers.re(rf'a state\.json file with the fingerprint of {quoted("name")}'))
def step_given_state_of_old_document(output_dir: Path, name: str) -> None:
    write_json(output_dir / STATE_FILE_NAME, {name: compute_fingerprint(OLD_TEXT)})


# Given: the documents that arrived since that build

@given(
    parsers.re(
        rf'the input directory contains {quoted("name")} with content matching its stored '
        rf'fingerprint'
    )
)
def step_given_unchanged_document(workdir: Path, name: str) -> None:
    write_document(workdir, name, OLD_TEXT)


@given(
    parsers.re(
        rf'the input directory contains {quoted("name")} with a fingerprint absent from '
        rf'state\.json$'
    )
)
def step_given_new_document(workdir: Path, name: str) -> None:
    write_document(workdir, name, NEW_TEXT)


# Given: what the model says about the new concepts

def proposed_class(state: dict, workdir: Path, name: str, resembles: str | None = None) -> None:
    """A class the model proposes is read out of a document the state knows nothing about."""
    state["class_names"] = [name]
    state["planned_classes"] = [name]
    state["instances_class"] = name
    if resembles is not None:
        state["resemblances"] = {name: (resembles, state["resemblance"])}
    if not (input_dir(workdir) / NEW_DOCUMENT).exists():
        write_document(workdir, NEW_DOCUMENT, NEW_TEXT)


@given(parsers.re(rf'the LLM returns a new class {quoted("name")}$'))
def step_given_llm_returns_new_class(state: dict, workdir: Path, name: str) -> None:
    proposed_class(state, workdir, name)


@given(
    parsers.re(
        rf'the LLM returns a new class {quoted("name")} whose embedding is similar to '
        rf'{quoted("other")} above the (?P<threshold>\d*\.\d+) threshold'
    )
)
def step_given_llm_returns_resembling_class(
    state: dict, workdir: Path, name: str, other: str, threshold: str
) -> None:
    state["resemblance"] = float(threshold) + 0.05
    proposed_class(state, workdir, name, resembles=other)


@given(
    parsers.re(
        rf'the LLM returns a new class {quoted("name")} whose embedding is similar to '
        rf'{quoted("other")} above the threshold$'
    )
)
def step_given_llm_returns_class_above_the_configured_threshold(
    state: dict, workdir: Path, name: str, other: str
) -> None:
    state["resemblance"] = BuilderConfig(mode="update").similarity_threshold + 0.05
    proposed_class(state, workdir, name, resembles=other)


@given(
    parsers.re(
        rf'the LLM returns a new class {quoted("name")} whose embedding similarity to '
        rf'{word("other")} is (?P<score>\d*\.\d+)$'
    )
)
def step_given_llm_returns_unrelated_class(
    state: dict, workdir: Path, name: str, other: str, score: str
) -> None:
    state["resemblance"] = float(score)
    proposed_class(state, workdir, name, resembles=other)


@given("the LLM confirms the two concepts are identical during merge verification")
def step_given_llm_confirms_the_merge(state: dict) -> None:
    state["merge_verified"] = True


@given("the LLM rejects the merge during verification because the concepts are distinct")
def step_given_llm_rejects_the_merge(state: dict) -> None:
    state["merge_verified"] = False
    state["parent"] = EXISTING_CLASS


@given(
    parsers.re(
        rf'the existing class {word("klass")} has the slot {quoted("slot")} of type '
        rf'{word("range")}$'
    )
)
def step_given_existing_slot_of_type(
    schema_path: Path, klass: str, slot: str, range: str
) -> None:
    document = read_yaml(schema_path)
    document["classes"][klass]["slots"] = [*document["classes"][klass]["slots"], slot]
    document["slots"][slot] = {
        "name": slot,
        "range": range,
        "annotations": document["slots"]["has_engine"]["annotations"],
    }
    write_yaml(schema_path, document)


@given("a new document suggests the type integer")
def step_given_new_document_suggests_a_type(state: dict, workdir: Path) -> None:
    state["class_names"] = []
    state["planned_classes"] = []
    state["relations"] = [WEIGHT_SLOT]
    state["slot_ranges"] = {WEIGHT_SLOT: PROPOSED_RANGE}
    if not (input_dir(workdir) / NEW_DOCUMENT).exists():
        write_document(workdir, NEW_DOCUMENT, NEW_TEXT)


@given("the LLM resolves the conflict")
def step_given_llm_resolves_the_conflict(state: dict) -> None:
    state["resolved_range"] = RESOLVED_RANGE

# When

@when("update mode runs")
def step_when_update_mode_runs(state: dict, workdir: Path, output_dir: Path) -> None:
    state.setdefault("class_names", [])
    state.setdefault("planned_classes", state["class_names"])
    state.setdefault("instances_class", EXISTING_CLASS)
    state["before"] = ontology_as_written(output_dir)
    state["client"] = client_for(state)
    build(
        input_dir(workdir),
        output_dir,
        BuilderConfig(mode="update"),
        state["client"],
        FakeEmbedder(state.get("resemblances", {})),
    )


# Then: what was and was not read

@then(parsers.re(rf'{quoted("name")} is not sent to the LLM$'))
def step_then_document_not_sent_to_the_llm(state: dict, name: str) -> None:
    assert not any(name in prompt for prompt in state["client"].prompts), "the model was asked"


@then("the ontology remains unchanged")
def step_then_ontology_remains_unchanged(state: dict, output_dir: Path) -> None:
    assert ontology_as_written(output_dir) == state["before"], "the ontology was rewritten"


@then(parsers.re(rf'a {quoted("event")} event is logged$'))
def step_then_event_is_logged(provenance_path: Path, event: str) -> None:
    event_named(provenance_path, event)


@then(parsers.re(rf'the fingerprint of {quoted("name")} is stored in state\.json$'))
def step_then_fingerprint_stored_in_state(output_dir: Path, name: str) -> None:
    stored = read_json(output_dir / STATE_FILE_NAME)
    text = OLD_TEXT if name == "old.txt" else NEW_TEXT
    assert stored[name] == compute_fingerprint(text), stored


@then(
    parsers.re(
        rf'merge verification is not performed for the pair '
        rf'{word("new")}/{word("existing")}$'
    )
)
def step_then_merge_not_verified(state: dict, new: str, existing: str) -> None:
    assert provenance_mentioning(state, new, existing) == [], f"{new}/{existing} were verified"


# Then: the classes of the extended T-Box

@then(parsers.re(r'the schema contains the classes (?P<names>.+)$'))
def step_then_schema_contains_classes(schema_path: Path, names: str) -> None:
    found = list(read_yaml(schema_path)["classes"])
    for name in split_names(names):
        assert name in found, f"{name} is missing from {found}"


@then(parsers.re(r'the schema contains both (?P<names>.+)$'))
def step_then_schema_contains_both_classes(schema_path: Path, names: str) -> None:
    step_then_schema_contains_classes(schema_path, names)


@then(parsers.re(rf'{word("klass")} is added as a new class$'))
def step_then_class_added(schema_path: Path, klass: str) -> None:
    assert klass in read_yaml(schema_path)["classes"]


@then(parsers.re(rf'the schema does not contain a new class {word("klass")}$'))
def step_then_schema_does_not_contain_class(schema_path: Path, klass: str) -> None:
    assert klass not in read_yaml(schema_path)["classes"]


@then(
    parsers.re(
        rf'the class {word("klass")} has its source_documents annotation extended with the '
        rf'new document$'
    )
)
def step_then_class_cites_the_new_document(schema_path: Path, klass: str) -> None:
    cited = cited_chunks(schema_path, klass)
    assert any(entry.endswith(f"{NEW_DOCUMENT}#c1") for entry in cited), cited
    assert any(entry.endswith("old.txt#c1") for entry in cited), cited


@then(
    parsers.re(
        rf'{word("klass")} is defined with "(?P<slot>\w+): (?P<parent>\w+)" when the LLM '
        rf'proposes that hierarchy$'
    )
)
def step_then_class_is_a(schema_path: Path, klass: str, slot: str, parent: str) -> None:
    definition = read_yaml(schema_path)["classes"][klass]
    assert definition[slot] == parent, definition


@then(
    parsers.re(
        rf'a {quoted("event")} event is recorded in the provenance log, mentioning both '
        rf'{word("merged")} and {word("surviving")}, with the source text excerpt$'
    )
)
def step_then_merge_event_recorded(
    provenance_path: Path, event: str, merged: str, surviving: str
) -> None:
    entry = event_named(provenance_path, event)
    assert entry["id"] == surviving, entry
    assert merged in entry["merged_ids"], entry
    assert entry["source_excerpt"], entry


# Then: the slots of the extended T-Box

@then(
    parsers.re(
        rf'the schema has a consistent {word("slot")} slot type matching the '
        rf'LLM decision$'
    )
)
def step_then_slot_type_follows_the_llm(state: dict, schema_path: Path, slot: str) -> None:
    written = read_yaml(schema_path)["slots"][slot]["range"]
    assert written == state["resolved_range"], written


@then(
    parsers.re(
        rf'a {quoted("event")} event is recorded in the provenance log with the source text '
        rf'excerpt$'
    )
)
def step_then_event_with_excerpt_recorded(provenance_path: Path, event: str) -> None:
    assert event_named(provenance_path, event)["source_excerpt"]


# Then: the A-Box of the extended ontology

@then("the existing instances are left untouched")
def step_then_existing_instances_untouched(state: dict, output_dir: Path) -> None:
    before = yaml.safe_load(state["before"]["instances.yaml"])
    after = read_yaml(output_dir / "instances.yaml")
    assert after["instances"][EXISTING_INSTANCE] == before["instances"][EXISTING_INSTANCE]
