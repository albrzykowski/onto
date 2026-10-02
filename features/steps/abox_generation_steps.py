import json
from pathlib import Path

import yaml
from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from pytest_bdd import given, parsers, then, when

from features.steps.support import FakeLLM, event_names, quoted, valid_config, word
from features.steps.tbox_generation_steps import extract_from
from features.steps.tbox_generation_steps import generate as generate_tbox
from onto.chunking import Chunk, chunk_document
from onto.ingestion import Document, compute_fingerprint
from onto.instance_gen import INSTANCES_FILE_NAME, generate_abox
from onto.provenance import ProvenanceLog

CHUNK_TEXT = "The Golf is produced by VW and has a 1.6 TDI engine"
EXCERPT = "The Golf is produced by VW and has a 1.6 TDI engine"
CHUNK = "corpus/article1.txt#c1"


def make_chunk() -> Chunk:
    document = Document(
        path=Path(CHUNK.rpartition("#")[0]),
        text=CHUNK_TEXT,
        fingerprint=compute_fingerprint(CHUNK_TEXT),
    )
    return chunk_document(document, valid_config())[0]


def instance_reply(name: str, klass: str, slots: dict[str, str]) -> str:
    return json.dumps(
        {"instances": [{"name": name, "class": klass, "slots": slots, "excerpt": EXCERPT}]}
    )


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
    def respond(_call: int) -> str:
        return state["reply"]

    return FakeLLM(respond)


def build(state: dict, provenance_path: Path) -> None:
    config = state.get("config") or valid_config()
    state["instances_path"] = generate_abox(
        [make_chunk()],
        config,
        client_for(state),
        Path(state["schema_path"]),
        ProvenanceLog(provenance_path, "override"),
    )
    state["document"] = yaml.safe_load(state["instances_path"].read_text(encoding="utf-8"))


def entries(state: dict) -> dict:
    return state["document"]["instances"]


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
    state["reply"] = instance_reply(name, klass, {slot: value})


@given(
    parsers.re(
        rf"the LLM returns an instance of the class {quoted('klass')} that is not in the T-Box"
    )
)
def step_given_llm_returns_instance_outside_the_tbox(
    state: dict, output_dir: Path, provenance_path: Path, klass: str
) -> None:
    tbox_of(state, output_dir, provenance_path, ["Vehicle"], ["has_engine"])
    state["reply"] = instance_reply("Mystery Thing", klass, {})


@given(parsers.re(r"a generated A-Box(?: and its T-Box)?"))
def step_given_generated_abox(state: dict, output_dir: Path, provenance_path: Path) -> None:
    tbox_of(state, output_dir, provenance_path, ["Vehicle"], ["has_engine"])
    state["reply"] = instance_reply("VW Golf", "Vehicle", {"has_engine": "1.6 TDI"})
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


# Then: provenance

@then("every instance has an annotation with its source document and chunk")
def step_then_every_instance_carries_provenance(state: dict) -> None:
    for name, entry in entries(state).items():
        annotations = entry["annotations"]
        assert annotations["source_documents"]["value"] == [CHUNK], name
