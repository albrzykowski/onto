import json
from pathlib import Path

import yaml
from pytest_bdd import given, parsers, then

from features.steps.support import (
    EXISTING_CLASS,
    EXISTING_INSTANCE,
    MERGE_MARKER,
    event_named,
    existing_instances,
    existing_schema,
    input_dir,
    ontology_as_written,
    quoted,
    read_yaml,
    split_names,
    valid_config,
    word,
    write_document,
    write_yaml,
)
from onto.builder import STATE_FILE_NAME
from onto.ingestion import compute_fingerprint

OLD_TEXT = "VW has been producing the Golf, a compact passenger car, since 1974."
NEW_TEXT = "The Passat has a six-speed manual transmission."
NEW_DOCUMENT = "new.txt"

WEIGHT_SLOT = "weight"
PROPOSED_RANGE = "integer"
RESOLVED_RANGE = "string"


def write_json(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cited_chunks(schema_path: Path, klass: str) -> list[str]:
    return read_yaml(schema_path)["classes"][klass]["annotations"]["source_documents"]["value"]


def provenance_mentioning(state: dict, first: str, second: str) -> list[str]:
    return [
        prompt
        for prompt in state["client"].prompts
        if MERGE_MARKER in prompt and first in prompt and second in prompt
    ]


# Background: the ontology an earlier build wrote

@given(parsers.re(rf'an existing ontology with a schema containing the class {word("klass")}$'))
def step_given_existing_ontology(state: dict, schema_path: Path) -> None:
    state["schema_path"] = schema_path
    write_yaml(schema_path, existing_schema())


@given(parsers.re(rf'the instance {quoted("name")}'))
def step_given_existing_instance(output_dir: Path) -> None:
    write_yaml(output_dir / "instances.yaml", existing_instances())


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
    state["resemblance"] = valid_config(mode="update").similarity_threshold + 0.05
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

# The step itself is in features/steps/support.py: abox-generation.feature runs an update too.


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
