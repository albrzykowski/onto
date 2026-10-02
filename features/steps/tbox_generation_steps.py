import json
import re
from pathlib import Path

import yaml
from linkml.linter.linter import Linter
from pytest_bdd import given, parsers, then, when

from features.steps.support import (
    FakeLLM,
    config_for,
    described,
    event_named,
    merged_description,
    quoted,
    split_names,
    word,
)
from onto.extraction import Candidate, CandidateKind
from onto.provenance import ProvenanceLog, SourceRef
from onto.schema_gen import generate_tbox

DEFAULT_CHUNK = "corpus/article1.txt#c1"
CORPUS_CLASSES = ["Vehicle", "Engine", "Manufacturer"]
CORPUS_SLOTS = ["has_engine", "produced_by"]


def candidate(
    kind: CandidateKind, name: str, chunk_id: str = DEFAULT_CHUNK, description: str = ""
) -> Candidate:
    return Candidate(
        kind=kind,
        name=name,
        source_documents=[SourceRef(path=Path(chunk_id.rpartition("#")[0]), chunk_id=chunk_id)],
        source_excerpt="The 1.6 TDI engine is installed in the Golf produced by VW",
        description=description,
    )


def only_description(name: str) -> str:
    """The only description the LLM ever gave for a class, so the schema's text is
    checkable against the model's reply rather than merely against being non-empty."""
    return f"A {name} as described by the language model."


def plan_reply(class_names: list[str], slot_names: list[str]) -> str:
    """A plan describes every class; only the first one carries the slots, so a schema
    that ignored the assignment instead of copying it would be visible in the output."""
    return json.dumps(
        {
            "classes": {
                name: {
                    "description": only_description(name),
                    "slots": slot_names if index == 0 else [],
                }
                for index, name in enumerate(class_names)
            }
        }
    )


def extract_from(state: dict, class_names: list[str], slot_names: list[str]) -> None:
    state["candidates"] = [
        *(candidate("class", name) for name in class_names),
        *(candidate("relation", name) for name in slot_names),
    ]
    state["reply"] = plan_reply(class_names, slot_names)


def client_for(state: dict) -> FakeLLM:
    """The plan comes first; a build that reconciles descriptions asks again afterwards."""
    def respond(call: int) -> str:
        if call and "merged" in state:
            return json.dumps({"descriptions": state["merged"]})
        return state["reply"]

    return FakeLLM(respond)


def generate(state: dict, output_dir: Path, log: ProvenanceLog) -> None:
    state["llm"] = client_for(state)
    state["schema_path"] = generate_tbox(
        state["candidates"], config_for(state), state["llm"], output_dir, log
    )
    state["document"] = yaml.safe_load(state["schema_path"].read_text(encoding="utf-8"))


def classes(state: dict) -> dict:
    return state["document"]["classes"]


def slots(state: dict) -> dict:
    return state["document"]["slots"]


def sources_of(state: dict, name: str) -> list[str]:
    return classes(state)[name]["annotations"]["source_documents"]["value"]


def reading(
    state: dict, kind: CandidateKind, name: str, chunk: str, description: str
) -> None:
    """One chunk's description of a concept, added to what the chunks before it said.

    Every step rebuilds the candidates and the answers from the readings so far, because the
    second chunk of a scenario is stated after the first one was already answered for.
    """
    readings = [*state.get("readings", []), (kind, name, chunk, description)]
    state["readings"] = readings
    state["candidates"] = [
        candidate(kind, concept, f"corpus/article{number}.txt#c{number}", said)
        for kind, concept, number, said in readings
    ]
    state["merged"] = {
        concept: merged_description(concept, texts)
        for concept, texts in stated_by_concept(readings).items()
    }
    state["reply"] = plan_reply(
        [concept for kind, concept, _, _ in readings if kind == "class"],
        [concept for kind, concept, _, _ in readings if kind == "relation"],
    )


def stated_by_concept(readings: list[tuple[CandidateKind, str, str, str]]) -> dict[str, list[str]]:
    """What each concept was described as, in the order the corpus described it."""
    stated: dict[str, list[str]] = {}
    for _, concept, _, description in readings:
        stated.setdefault(concept, []).append(description)
    return stated


def reconciled_from(state: dict, concept: str) -> bool:
    """A reconciliation is only a merge if the model was given every reading it reconciles."""
    return all(
        description in state["llm"].prompts[-1]
        for description in stated_by_concept(state["readings"])[concept]
    )


# Given: what the LLM returned

@given(
    parsers.re(
        r"the LLM has returned the class candidates (?P<classes>[\w, ]+?) "
        r"and the relations (?P<relations>[\w, ]+?)\s*$"
    )
)
def step_given_llm_returned_candidates(state: dict, classes: str, relations: str) -> None:
    extract_from(state, split_names(classes), split_names(relations))


@given(
    parsers.re(
        r"candidates from (?P<count>\d+) independent chunks containing the repeated "
        r"class (?P<name>\w+)"
    )
)
def step_given_repeated_candidate(state: dict, count: str, name: str) -> None:
    state["candidates"] = [
        candidate("class", name, f"corpus/article{number}.txt#c{number}")
        for number in range(1, int(count) + 1)
    ]
    state["reply"] = plan_reply([name], [])


@given(
    parsers.re(
        rf"the LLM returns the class {word('klass')} and the relation {word('slot')} "
        rf"from one chunk"
    )
)
def step_given_llm_returned_class_and_relation_from_one_chunk(
    state: dict, klass: str, slot: str
) -> None:
    extract_from(state, [klass], [slot])


@given(
    parsers.re(
        rf"a configuration with allowed_relations containing the relation {quoted('name')}"
    )
)
def step_given_configuration_with_allowed_relation(state: dict, name: str) -> None:
    config_for(state).allowed_relations = described(f'{name} as "stated by the configuration"')


@given(
    parsers.re(
        rf"the LLM has returned the class candidate {quoted('name')} and the relations "
        rf"(?P<relations>\"[^\"]+\"(?:\s*,\s*\"[^\"]+\")*)\s*$"
    )
)
def step_given_llm_returned_one_class_candidate(state: dict, name: str, relations: str) -> None:
    extract_from(state, [name], re.findall(r'"([^"]+)"', relations))


@given(
    parsers.re(
        rf"the LLM returns the class {word('klass')} from chunk#(?P<chunk>\d+) with "
        rf"description {quoted('description')}"
    )
)
def step_given_llm_returned_class_from_chunk_with_description(
    state: dict, klass: str, chunk: str, description: str
) -> None:
    reading(state, "class", klass, chunk, description)


@given(
    parsers.re(
        rf"the LLM returns the relation {word('slot')} from chunk#(?P<chunk>\d+) with "
        rf"description {quoted('description')}"
    )
)
def step_given_llm_returned_relation_from_chunk_with_description(
    state: dict, slot: str, chunk: str, description: str
) -> None:
    reading(state, "relation", slot, chunk, description)


@given("a generated T-Box")
def step_given_generated_tbox(state: dict, output_dir: Path, provenance_path: Path) -> None:
    if not state["candidates"]:
        extract_from(state, CORPUS_CLASSES, CORPUS_SLOTS)
    generate(state, output_dir, ProvenanceLog(provenance_path, "override"))


# When

@when("the T-Box is generated")
def step_when_tbox_is_generated(state: dict, output_dir: Path, provenance_path: Path) -> None:
    generate(state, output_dir, ProvenanceLog(provenance_path, "override"))


@when("the schema is validated")
def step_when_schema_is_validated(state: dict) -> None:
    problems = Linter().lint(str(state["schema_path"]), validate_schema=True)
    state["lint_errors"] = [
        str(problem) for problem in problems if problem.level.code.text == "error"
    ]


# Then: the file

@then('the file "schema.yaml" is saved in the output directory')
def step_then_schema_file_saved_in_output_directory(state: dict, schema_path: Path) -> None:
    assert state["schema_path"] == schema_path, state["schema_path"]
    assert schema_path.exists()


@then('the document contains LinkML-compliant "id" and "name" fields')
def step_then_document_has_id_and_name(state: dict) -> None:
    for field in ("id", "name"):
        assert state["document"].get(field), f"the schema has no {field}"


# Then: the contents

@then(parsers.re(r"it contains the class definitions (?P<names>[\w, ]+?)\s*$"))
def step_then_contains_class_definitions(state: dict, names: str) -> None:
    found = list(classes(state))
    for name in split_names(names):
        assert name in found, f"{name} missing from {found}"


@then(parsers.re(rf'the class {word("name")} has the slot {quoted("slot")}\s*$'))
def step_then_class_has_slot(state: dict, name: str, slot: str) -> None:
    assert slot in classes(state)[name]["slots"], classes(state)[name]["slots"]


@then(parsers.re(rf"the class {word('name')} has the slot {quoted('slot')} only\s*$"))
def step_then_class_has_slot_only(state: dict, name: str, slot: str) -> None:
    assigned = classes(state)[name]["slots"]
    assert assigned == [slot], assigned


@then(
    parsers.re(
        rf'a {quoted("event")} event with the reason {quoted("reason")} is recorded '
        rf"for {word('name')}\s*$"
    )
)
def step_then_rejection_recorded_for(
    provenance_path: Path, event: str, reason: str, name: str
) -> None:
    entry = event_named(provenance_path, event)
    assert entry["reason"] == reason, entry
    assert entry["id"] == name, entry


@then("it passes linkml validation without errors")
def step_then_passes_linkml_validation(state: dict) -> None:
    assert state["lint_errors"] == [], state["lint_errors"]


# Then: descriptions and provenance

@then('every class has a "description" provided by the LLM')
def step_then_every_class_has_a_description(state: dict) -> None:
    for name, definition in classes(state).items():
        assert definition["description"] == only_description(name), definition


@then('every class has a "source_documents" annotation pointing to its source document')
def step_then_every_class_has_source_documents(state: dict) -> None:
    known = {ref.chunk_id for item in state["candidates"] for ref in item.source_documents}
    for name in classes(state):
        cited = sources_of(state, name)
        assert cited, f"{name} cites no chunk"
        assert set(cited) <= known, f"{name} cites chunks it was not extracted from: {cited}"


@then(parsers.re(r"the schema contains exactly one class (?P<name>\w+)"))
def step_then_schema_contains_one_class(state: dict, name: str) -> None:
    assert list(classes(state)) == [name], list(classes(state))


@then(
    parsers.re(
        rf'an {quoted("event")} event for {word("name")} is recorded with the chunk and '
        rf"the excerpt"
    )
)
def step_then_event_for_name_recorded_with_excerpt(
    provenance_path: Path, event: str, name: str
) -> None:
    entry = event_named(provenance_path, event)
    assert entry["id"] == name, entry
    assert entry["source_documents"], entry
    assert entry["source_excerpt"], entry


@then(
    parsers.re(
        r"the source_documents annotation of (?P<name>\w+) lists all (?P<count>\d+) chunks"
    )
)
def step_then_annotation_lists_all_chunks(state: dict, name: str, count: str) -> None:
    assert sources_of(state, name) == [
        f"corpus/article{number}.txt#c{number}" for number in range(1, int(count) + 1)
    ], sources_of(state, name)


@then(parsers.re(rf"the class {word('name')} has a description merged from both chunks"))
def step_then_class_description_merged_from_both_chunks(state: dict, name: str) -> None:
    definition = classes(state)[name]
    assert definition["description"] == state["merged"][name], definition
    assert reconciled_from(state, name), state["llm"].prompts[-1]


@then(parsers.re(rf"the slot {word('name')} has a description merged from both chunks"))
def step_then_slot_description_merged_from_both_chunks(state: dict, name: str) -> None:
    definition = slots(state)[name]
    assert definition["description"] == state["merged"][name], definition
    assert reconciled_from(state, name), state["llm"].prompts[-1]


@then(parsers.re(rf'an {quoted("event")} event is recorded with the merged description'))
def step_then_event_recorded_with_merged_description(
    state: dict, provenance_path: Path, event: str
) -> None:
    entry = event_named(provenance_path, event)
    assert entry["description"] == state["merged"][entry["id"]], entry
