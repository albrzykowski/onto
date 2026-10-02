import json
from pathlib import Path
from typing import Any

import yaml
from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from pytest_bdd import given, parsers, then, when

from features.steps.support import (
    FakeLLM,
    event_named,
    event_names,
    existing_instances,
    merged_description,
    quoted,
    read_yaml,
    valid_config,
    word,
    write_document,
    write_yaml,
)
from features.steps.tbox_generation_steps import extract_from
from features.steps.tbox_generation_steps import generate as generate_tbox
from onto.chunking import Chunk, chunk_document
from onto.ingestion import Document, compute_fingerprint
from onto.instance_gen import INSTANCES_FILE_NAME, _identifier, generate_abox
from onto.provenance import ProvenanceLog

CHUNK_TEXT = "The Golf is produced by VW and has a 1.6 TDI engine"
EXCERPT = "The Golf is produced by VW and has a 1.6 TDI engine"
CHUNK = "corpus/article1.txt#c1"
NEW_DOCUMENT = "new.txt"
NEW_TEXT = "The Golf is sold with the 1.6 TDI engine and a manual gearbox."


def make_chunk(chunk_id: str = CHUNK) -> Chunk:
    document = Document(
        path=Path(chunk_id.rpartition("#")[0]),
        text=CHUNK_TEXT,
        fingerprint=compute_fingerprint(CHUNK_TEXT),
    )
    return chunk_document(document, valid_config())[0]


def instance_reply(*instances: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "instances": [
                {"name": name, "class": klass, "slots": slots, "excerpt": EXCERPT}
                for name, klass, slots in instances
            ]
        }
    )


def described_reply(reading: dict[str, Any]) -> str:
    """The instances one chunk stated, each with the description that chunk gave it."""
    return json.dumps(
        {
            "instances": [
                {
                    "name": reading["name"],
                    "class": reading["class"],
                    "slots": reading["slots"],
                    "description": reading["description"],
                    "excerpt": EXCERPT,
                }
            ]
        }
    )


def remember(state: dict, *instances: tuple[str, str, dict[str, str]]) -> None:
    """A scenario states what the model returns one instance at a time, so each step adds
    to the answer instead of replacing the one before it."""
    state.setdefault("instances", []).extend(instances)


def tbox_of(
    state: dict,
    output_dir: Path,
    provenance_path: Path,
    class_names: list[str],
    slot_names: list[str],
) -> None:
    """Instances are only meaningful against a T-Box, so the scenarios that do not name
    one get the schema the feature talks about."""
    extract_from(state, class_names, slot_names)
    generate_tbox(state, output_dir, ProvenanceLog(provenance_path, "override"))


def client_for(state: dict) -> FakeLLM:
    """One request per chunk, each answered with the instances that chunk stated, and a
    request after them that reconciles whatever several of the chunks described."""
    readings: list[dict[str, Any]] = state.get("readings", [])

    def respond(call: int) -> str:
        if not readings:
            return instance_reply(*state["instances"])
        if call < len(readings):
            return described_reply(readings[call])
        return json.dumps({"descriptions": state["merged"]})

    return FakeLLM(respond)


def chunks_of(state: dict) -> list[Chunk]:
    """One chunk per reading the scenario named, and the single chunk every other scenario
    of this feature builds from."""
    return [make_chunk(reading["chunk"]) for reading in state.get("readings", [])] or [
        make_chunk()
    ]


def build(state: dict, provenance_path: Path) -> None:
    config = state.get("config") or valid_config()
    state["llm"] = client_for(state)
    state["instances_path"] = generate_abox(
        chunks_of(state),
        config,
        state["llm"],
        Path(state["schema_path"]),
        ProvenanceLog(provenance_path, "override"),
    )
    state["document"] = yaml.safe_load(state["instances_path"].read_text(encoding="utf-8"))


def entries(state: dict) -> dict:
    return state["document"]["instances"]


def written_instances(output_dir: Path) -> dict:
    """The A-Box as it stands on disk, for the scenarios an update wrote rather than a When
    step of this module."""
    return read_yaml(output_dir / INSTANCES_FILE_NAME)["instances"]


def validate(state: dict) -> None:
    """LinkML's own jsonschema plugin, one entry at a time: the file is keyed by instance
    id, so the class an entry must conform to is the one that entry declares."""
    validator = Validator(
        state["schema_path"], validation_plugins=[JsonschemaValidationPlugin()]
    )
    problems: list[str] = []
    for entry in entries(state).values():
        report = validator.validate(entry, target_class=entry["class"])
        problems.extend(str(result.message) for result in report.results)
    state["violations"] = problems


# Given: the T-Box and what the model returns

@given(
    parsers.re(
        rf"a generated T-Box with the classes {word('first')} and {word('second')} "
        rf"and the slot {word('slot')}"
    )
)
def step_given_generated_tbox_with_two_classes(
    state: dict, output_dir: Path, provenance_path: Path, first: str, second: str, slot: str
) -> None:
    tbox_of(state, output_dir, provenance_path, [first, second], [slot])


@given(parsers.re(rf"a generated T-Box with the class {word('klass')}\s*$"))
def step_given_generated_tbox_with_class(
    state: dict, output_dir: Path, provenance_path: Path, klass: str
) -> None:
    tbox_of(state, output_dir, provenance_path, [klass], [])


@given(
    parsers.re(
        rf"a generated T-Box with the class {word('klass')} and the slot {word('slot')}"
    )
)
def step_given_generated_tbox_with_class_and_slot(
    state: dict, output_dir: Path, provenance_path: Path, klass: str, slot: str
) -> None:
    tbox_of(state, output_dir, provenance_path, [klass], [slot])


@given(
    parsers.re(
        rf"the LLM returns the instance {quoted('name')} of class {word('klass')} with "
        rf"{word('slot')} pointing to {quoted('value')}"
    )
)
def step_given_llm_returns_instance_with_slot(
    state: dict, name: str, klass: str, slot: str, value: str
) -> None:
    remember(state, (name, klass, {slot: value}))


@given(
    parsers.re(
        rf"the LLM returns the instance {quoted('name')} of class {word('klass')} from "
        rf"chunk#(?P<chunk>\d+) with description {quoted('description')}"
    )
)
def step_given_llm_returns_instance_from_chunk_with_description(
    state: dict, name: str, klass: str, chunk: str, description: str
) -> None:
    """One chunk's reading of an entity, added to what the chunks before it said.

    The reconciliation is keyed by the id the entity is written under, because that is what
    both the instances and the log are keyed by.
    """
    state.setdefault("readings", []).append(
        {
            "chunk": f"corpus/article{chunk}.txt#c{chunk}",
            "name": name,
            "class": klass,
            "slots": {},
            "description": description,
        }
    )
    stated: dict[str, list[str]] = {}
    for reading in state["readings"]:
        stated.setdefault(_identifier(reading["name"]), []).append(reading["description"])
    state["stated"] = stated
    state["merged"] = {
        entity: merged_description(entity, texts) for entity, texts in stated.items()
    }


@given(
    parsers.re(rf"the LLM returns the instance {quoted('name')} of class {word('klass')}\s*$")
)
def step_given_llm_returns_instance(state: dict, name: str, klass: str) -> None:
    remember(state, (name, klass, {}))


@given(
    parsers.re(
        rf"the LLM returns the instance {quoted('name')} of class {word('klass')} "
        rf"with no slot values\s*$"
    )
)
def step_given_llm_returns_instance_without_slots(state: dict, name: str, klass: str) -> None:
    """An update is answered by the double in support.py, which reads the state this step
    fills rather than a whole reply."""
    state["instance_name"] = name
    state["instances_class"] = klass


@given(
    parsers.re(
        rf"the LLM returns the instances {quoted('first')} and {quoted('second')} "
        rf"of class {word('klass')}\s*$"
    )
)
def step_given_llm_returns_two_instances(
    state: dict, first: str, second: str, klass: str
) -> None:
    remember(state, (first, klass, {}), (second, klass, {}))


@given(
    parsers.re(
        rf"an existing A-Box in which {word('name')} has the slot {word('slot')} "
        rf"with the value {quoted('value')}"
    )
)
def step_given_existing_abox_with_slot(
    workdir: Path, output_dir: Path, name: str, slot: str, value: str
) -> None:
    """The A-Box the previous build wrote, plus the document the update is about to read:
    both are the world an update runs against, and neither is stated by another step of this
    feature."""
    previous = existing_instances()["instances"]
    assert name in previous and previous[name][slot] == value, previous
    write_yaml(output_dir / INSTANCES_FILE_NAME, existing_instances())
    write_document(workdir, NEW_DOCUMENT, NEW_TEXT)


@given(
    parsers.re(
        rf"the LLM returns an instance of the class {quoted('klass')} that is not in the T-Box"
    )
)
def step_given_llm_returns_instance_outside_the_tbox(
    state: dict, output_dir: Path, provenance_path: Path, klass: str
) -> None:
    tbox_of(state, output_dir, provenance_path, ["Vehicle"], ["has_engine"])
    remember(state, ("Mystery Thing", klass, {}))


@given(parsers.re(r"a generated A-Box(?: and its T-Box)?"))
def step_given_generated_abox(state: dict, output_dir: Path, provenance_path: Path) -> None:
    tbox_of(state, output_dir, provenance_path, ["Vehicle"], ["has_engine"])
    remember(state, ("VW Golf", "Vehicle", {"has_engine": "1.6 TDI"}))
    build(state, provenance_path)


# When

@when("the A-Box is generated")
def step_when_abox_is_generated(state: dict, provenance_path: Path) -> None:
    build(state, provenance_path)


@when("the instances are validated against the schema")
def step_when_instances_validated_against_the_schema(state: dict) -> None:
    validate(state)


# Then: the file and its entries

@then(parsers.re(rf'the file {quoted("name")} is saved in the output directory'))
def step_then_file_saved_in_output_directory(state: dict, output_dir: Path, name: str) -> None:
    assert name == INSTANCES_FILE_NAME
    assert state["instances_path"] == output_dir / name, state["instances_path"]
    assert state["instances_path"].exists()


@then(parsers.re(rf'it contains the instance {quoted("name")} of class {word("klass")}'))
def step_then_contains_instance_of_class(state: dict, name: str, klass: str) -> None:
    found = entries(state)
    assert name in found, list(found)
    assert found[name]["class"] == klass
    state["checked"] = name


@then(
    parsers.re(rf'the instance has the slot {word("slot")} with the value {quoted("value")}')
)
def step_then_instance_has_slot_with_value(state: dict, slot: str, value: str) -> None:
    entry = entries(state)[state["checked"]]
    assert entry[slot] == value, entry


@then(parsers.re(r"the LLM prompt states a limit of (?P<limit>\d+) instances"))
def step_then_prompt_states_instance_limit(state: dict, limit: str) -> None:
    prompt = state["llm"].prompts[0]
    assert f"At most {limit} instances" in prompt


@then("the LLM prompt states that a slot value is a single string and never a list")
def step_then_prompt_requires_single_string_slot(state: dict) -> None:
    prompt = state["llm"].prompts[0]
    assert "single string" in prompt and "never a list" in prompt


@then("they pass LinkML schema-conformance validation without errors")
def step_then_pass_linkml_schema_conformance(state: dict) -> None:
    assert state["violations"] == [], state["violations"]


@then(parsers.re(rf"the {word('klass')} instance is not written to instances.yaml"))
def step_then_outside_class_instance_not_written(state: dict, klass: str) -> None:
    assert all(entry["class"] != klass for entry in entries(state).values()), entries(state)


@then(parsers.re(rf'an {quoted("event")} event is recorded in the provenance log'))
def step_then_event_recorded_in_provenance_log(event: str, provenance_path: Path) -> None:
    assert event in event_names(provenance_path), event_names(provenance_path)


@then(
    parsers.re(rf'the instance {quoted("name")} is written\s*$')
)
def step_then_instance_is_written(state: dict, name: str) -> None:
    assert name in entries(state), list(entries(state))
    state["checked"] = name


@then(parsers.re(rf"the instance has no slot {word('slot')}\s*$"))
def step_then_instance_has_no_slot(state: dict, slot: str) -> None:
    entry = entries(state)[state["checked"]]
    assert slot not in entry, entry


@then(
    parsers.re(
        rf'an {quoted("event")} event with the reason {quoted("reason")} is recorded '
        rf"for the value {quoted('value')}"
    )
)
def step_then_rejection_recorded_for_value(
    provenance_path: Path, event: str, reason: str, value: str
) -> None:
    entry = event_named(provenance_path, event)
    assert entry["reason"] == reason, entry
    assert entry["value"] == value, entry


@then(parsers.re(rf"one instance {word('name')} is written"))
def step_then_one_instance_is_written(state: dict, name: str) -> None:
    assert list(entries(state)) == [name], entries(state)


@then(
    parsers.re(
        rf'an {quoted("event")} event with the reason {quoted("reason")} is recorded\s*$'
    )
)
def step_then_event_with_reason_recorded(provenance_path: Path, event: str, reason: str) -> None:
    assert event_named(provenance_path, event)["reason"] == reason


# Then: provenance

@then(parsers.re(rf"the instance {word('name')} has a description merged from both chunks"))
def step_then_instance_description_merged_from_both_chunks(state: dict, name: str) -> None:
    entry = entries(state)[name]
    assert entry["description"] == state["merged"][name], entry
    prompt = state["llm"].prompts[-1]
    assert all(text in prompt for text in state["stated"][name]), prompt


@then(parsers.re(rf'an {quoted("event")} event is recorded with the merged description'))
def step_then_event_recorded_with_merged_description(
    state: dict, provenance_path: Path, event: str
) -> None:
    entry = event_named(provenance_path, event)
    assert entry["description"] == state["merged"][entry["id"]], entry


@then("every instance has an annotation with its source document and chunk")
def step_then_every_instance_carries_provenance(state: dict) -> None:
    for name, entry in entries(state).items():
        annotations = entry["annotations"]
        assert annotations["source_documents"]["value"] == [CHUNK], name


@then(
    parsers.re(
        rf'an {quoted("event")} event for {word("name")} is recorded with the chunk and '
        rf"the excerpt in the provenance log"
    )
)
def step_then_event_with_excerpt_for_instance_recorded(
    provenance_path: Path, event: str, name: str
) -> None:
    entry = event_named(provenance_path, event)
    assert entry["id"] == name, entry
    assert entry["source_documents"], entry
    assert entry["source_excerpt"], entry


# Then: an instance an update extended

@then(
    parsers.re(
        rf"the instance {word('name')} still has the slot {word('slot')} with the "
        rf"value {quoted('value')}"
    )
)
def step_then_instance_still_has_slot_with_value(
    output_dir: Path, name: str, slot: str, value: str
) -> None:
    entry = written_instances(output_dir)[name]
    assert entry[slot] == value, entry


@then("its source_documents annotation cites the new document")
def step_then_source_documents_cite_the_new_document(output_dir: Path) -> None:
    cited = written_instances(output_dir)["VW_Golf"]["annotations"]["source_documents"]["value"]
    assert f"corpus/{NEW_DOCUMENT}#c1" in cited, cited


@then(parsers.re(rf'an {quoted("event")} event for {word("name")} is recorded\s*$'))
def step_then_event_for_instance_recorded(provenance_path: Path, event: str, name: str) -> None:
    assert event_named(provenance_path, event)["id"] == name


