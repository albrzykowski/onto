import json
from pathlib import Path

import yaml
from pytest_bdd import given, parsers, then, when

from features.steps.support import FakeLLM, log_events, quoted, word
from onto.builder import STATE_FILE_NAME, build
from onto.config import BuilderConfig
from onto.ingestion import load_documents
from onto.provenance import ProvenanceLog

CORPUS = "corpus"
EXCERPT = "The Golf is produced by VW and has a 1.6 TDI engine"
UNKNOWN_CLASS = "ClassTheSchemaDoesNotHave"
DEFAULT_CLASSES = ["Vehicle"]


def input_dir(workdir: Path) -> Path:
    return workdir / CORPUS


def write_document(workdir: Path, name: str) -> None:
    """A text of its own per document, so a fingerprint identifies which file it came from."""
    corpus = input_dir(workdir)
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / name).write_text(f"{EXCERPT}, as document {name} states.", encoding="utf-8")


def current_fingerprints(workdir: Path) -> dict[str, str]:
    """What a build records in its state: every document of the corpus, by its name in it."""
    corpus = input_dir(workdir)
    return {
        document.path.relative_to(corpus).as_posix(): document.fingerprint
        for document in load_documents(corpus)
    }


def write_json(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classes_of(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("classes", {})


def client_for(state: dict) -> FakeLLM:
    """The build asks the model three different things; the double answers each by what the
    prompt asks for, so no scenario depends on the order the calls happen to come in.

    The instance generator is answered with a class the schema does not have, so the build
    logs an event of its own and "the log starts from scratch" has something to be checked
    against.
    """
    names = state["class_names"]

    def concepts() -> str:
        return json.dumps(
            {
                "classes": [{"name": name, "excerpt": EXCERPT} for name in names],
                "relations": [],
            }
        )

    def plan() -> str:
        return json.dumps(
            {
                "classes": {
                    name: {"description": f"A {name} as the model described it.", "slots": []}
                    for name in names
                }
            }
        )

    def instances() -> str:
        return json.dumps(
            {
                "instances": [
                    {"name": "Phantom", "class": UNKNOWN_CLASS, "slots": {}, "excerpt": EXCERPT}
                ]
            }
        )

    def respond(call: int) -> str:
        prompt = client.prompts[call]
        if "Candidate classes:" in prompt:
            return plan()
        if "Classes of the schema:" in prompt:
            return instances()
        return concepts()

    client = FakeLLM(respond)
    return client


# Given: the ontology that is about to be replaced

@given(
    parsers.re(
        rf'the output directory contains an old {quoted("name")} with the class {quoted("klass")}'
    )
)
def step_given_output_contains_old_schema(
    state: dict, output_dir: Path, name: str, klass: str
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / name).write_text(
        yaml.safe_dump(
            {
                "id": "https://example.org/old-schema",
                "name": "old-schema",
                "classes": {klass: {"name": klass}},
            }
        ),
        encoding="utf-8",
    )
    # the ontology being replaced is more than its schema: the log of the build that wrote
    # it is stale too, and only the log of this build may survive
    ProvenanceLog(output_dir / "provenance.jsonl", "override").record(
        event="class.created", id=klass, source_excerpt="The class of the previous build."
    )
    state["old_class"] = klass


# Given: the documents and what the model returns

@given(parsers.re(rf'the input directory contains {quoted("name")}$'))
def step_given_input_contains_document(workdir: Path, name: str) -> None:
    write_document(workdir, name)


@given(parsers.re(rf'the LLM returns the class {quoted("klass")}'))
def step_given_llm_returns_class(state: dict, klass: str) -> None:
    state["class_names"] = [klass]


@given("state.json contains old fingerprints")
def step_given_state_contains_old_fingerprints(output_dir: Path) -> None:
    write_json(output_dir / STATE_FILE_NAME, {"old.txt": "0" * 64})


@given(
    parsers.re(
        r"the input directory contains (?P<count>\d+) documents whose fingerprints are "
        r"present in state.json"
    )
)
def step_given_input_documents_already_recorded_in_state(
    state: dict, workdir: Path, output_dir: Path, count: str
) -> None:
    for number in range(1, int(count) + 1):
        write_document(workdir, f"doc{number}.txt")
    write_json(output_dir / STATE_FILE_NAME, current_fingerprints(workdir))
    state["class_names"] = ["Vehicle", "Manufacturer"]


# When

@when("override mode runs")
def step_when_override_mode_runs(state: dict, workdir: Path, output_dir: Path) -> None:
    """The scenarios that name no document still need something to build from."""
    if not list(input_dir(workdir).glob("*")):
        write_document(workdir, "new.txt")
    state.setdefault("class_names", DEFAULT_CLASSES)
    state["client"] = client_for(state)
    build(input_dir(workdir), output_dir, BuilderConfig(mode="override"), state["client"])


# Then: the schema that replaced the old one

@then(parsers.re(rf'the new {quoted("name")} does not contain the class {word("klass")}'))
def step_then_new_file_does_not_contain_class(output_dir: Path, name: str, klass: str) -> None:
    assert klass not in classes_of(output_dir / name), classes_of(output_dir / name)


@then(parsers.re(rf'it contains the class {word("klass")}'))
def step_then_schema_contains_the_class(schema_path: Path, klass: str) -> None:
    assert klass in classes_of(schema_path), classes_of(schema_path)


# Then: the state and the log the previous build left behind

@then("state.json contains only fingerprints from the current build")
def step_then_state_contains_only_current_fingerprints(
    workdir: Path, output_dir: Path
) -> None:
    written = json.loads((output_dir / STATE_FILE_NAME).read_text(encoding="utf-8"))
    assert written == current_fingerprints(workdir), written


@then("the provenance log starts from scratch")
def step_then_provenance_log_starts_from_scratch(provenance_path: Path) -> None:
    events = log_events(provenance_path) if provenance_path.exists() else []
    assert [event["id"] for event in events] == ["Phantom"], events


@then("both documents are sent to the LLM")
def step_then_both_documents_are_sent_to_the_llm(state: dict, workdir: Path) -> None:
    prompts = "\n".join(state["client"].prompts)
    for document in load_documents(input_dir(workdir)):
        assert str(document.path) in prompts, f"{document.path} was never sent"
