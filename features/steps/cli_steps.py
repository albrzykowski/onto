"""Step definitions for the command-line interface feature."""

import contextlib
import io
import json
import shlex
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, parsers, then, when

from features.steps.support import VALID_CONFIG, FakeLLM, quoted, valid_config
from onto.builder import build
from onto.cli import main
from onto.config import BuilderConfig
from onto.schema_gen import SCHEMA_FILE_NAME

EXCERPT = "The Golf is produced by VW and has a 1.6 TDI engine"

FIRST_CLASS = "Vehicle"
SECOND_CLASS = "Engine"
UNKNOWN_CLASS = "ClassTheSchemaDoesNotHave"
EXISTING_INSTANCE = "VW_Golf"
NEW_INSTANCE = "VW Passat"
FIRST_TEXT = "VW has been producing the Golf, a compact passenger car, since 1974."
SECOND_TEXT = "The Passat has a six-speed manual transmission."

INSTANCES_FILE = "instances.yaml"

BUILT_CLASSES = [FIRST_CLASS, SECOND_CLASS]
EXTENDED_CLASSES = [SECOND_CLASS]


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def write_document(workdir: Path, directory: str, text: str) -> None:
    corpus = workdir / directory
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / "document.txt").write_text(text, encoding="utf-8")


def client_for(classes: list[str], instance: str, instance_class: str) -> FakeLLM:
    """A build asks the model three different things; the double answers each by what the
    prompt asks for, so no scenario depends on the order the calls happen to come in.

    What a given run of the model returns is an argument rather than shared state, so the
    earlier build of a scenario cannot answer for the command that follows it.
    """

    def concepts() -> str:
        return json.dumps(
            {
                "classes": [{"name": name, "excerpt": EXCERPT} for name in classes],
                "relations": [],
            }
        )

    def plan() -> str:
        return json.dumps(
            {
                "classes": {
                    name: {"description": f"A {name} as the model described it.", "slots": []}
                    for name in classes
                }
            }
        )

    def instances() -> str:
        """One instance of a class the schema has, and one of a class it does not: the
        rejected one is what the provenance log records, and a log only comes into being when
        something is written to it."""
        return json.dumps(
            {
                "instances": [
                    {"name": instance, "class": instance_class, "slots": {}, "excerpt": EXCERPT},
                    {
                        "name": "Phantom",
                        "class": UNKNOWN_CLASS,
                        "slots": {},
                        "excerpt": EXCERPT,
                    },
                ]
            }
        )

    def respond(call: int) -> str:
        prompt = client.prompts[call]
        if "Candidate classes:" in prompt or "New concepts:" in prompt:
            return plan()
        if "Classes of the schema:" in prompt:
            return instances()
        return concepts()

    client = FakeLLM(respond)
    return client


class DistinctEmbedder:
    """Every text gets an axis of its own, so nothing resembles anything else: what these
    scenarios are about is the command reaching the build, not the merge it may decide on."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [[0.0] * len(texts) for _ in texts]
        for index in range(len(texts)):
            vectors[index][index] = 1.0
        return vectors


def run_command(state: dict, arguments: str) -> None:
    """Run the command the way a shell runs it.

    argparse reports a usage error by writing to stderr and exiting, so the exit code and the
    output are collected here the way the shell would collect them.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = main(shlex.split(arguments))
        except SystemExit as exit_request:
            code = 0 if exit_request.code is None else int(exit_request.code)
    state["exit_code"] = code
    state["stdout"] = stdout.getvalue()
    state["stderr"] = stderr.getvalue()


def stand_in_for_the_provider(state: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """The command reaches the build with the model and the embedder the scenario prepared, so
    no step of it calls a provider over the network.

    Each factory is replaced on its own: the command asks for a model and an embedder, and
    they are not the same stand-in.
    """

    def this_model(_config: BuilderConfig) -> FakeLLM:
        return state["llm"]

    def this_embedder(_config: BuilderConfig) -> DistinctEmbedder:
        return state["embedder"]

    monkeypatch.setattr("onto.cli.llm_for", this_model)
    monkeypatch.setattr("onto.cli.embedder_for", this_embedder)


# Given: the input a build reads

@given(parsers.re(rf'a directory {quoted("name")} with the file {quoted("file")}'))
def step_given_directory_with_file(workdir: Path, name: str, file: str) -> None:
    corpus = workdir / name
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / file).write_text(EXCERPT, encoding="utf-8")


@given(parsers.re(rf'a new document in the directory {quoted("name")}'))
def step_given_new_document(state: dict, workdir: Path, name: str) -> None:
    write_document(workdir, name, SECOND_TEXT)
    state["new_class_names"] = EXTENDED_CLASSES
    state["new_instance"] = NEW_INSTANCE
    state["new_instance_class"] = SECOND_CLASS


@given(parsers.re(rf'a configuration file {quoted("name")} with mode {quoted("mode")}'))
def step_given_configuration_file(workdir: Path, name: str, mode: str) -> None:
    write_yaml(workdir / name, {**VALID_CONFIG, "mode": mode, "model": "mistral-large-latest"})


@given(parsers.re(rf'an existing ontology in the directory {quoted("name")}'))
def step_given_existing_ontology(workdir: Path, name: str) -> None:
    """What an earlier build wrote, produced by that build rather than written by hand, so the
    update is handed a schema, a provenance log and a state to extend."""
    write_document(workdir, "corpus", FIRST_TEXT)
    write_yaml(
        workdir / "config.yaml",
        {**VALID_CONFIG, "mode": "override", "model": "mistral-large-latest"},
    )
    build(
        input_dir=workdir / "corpus",
        output_dir=workdir / name,
        config=valid_config(mode="override"),
        llm=client_for([FIRST_CLASS], EXISTING_INSTANCE, FIRST_CLASS),
    )


# When: a command runs

@when("I run `onto build` without arguments")
def step_when_build_runs_without_arguments(state: dict) -> None:
    run_command(state, "build")


@when(parsers.re(r'I run `(?P<command>[^`]+)`$'))
def step_when_command_runs(
    state: dict, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    state["llm"] = client_for(
        state.get("new_class_names", BUILT_CLASSES),
        state.get("new_instance", NEW_INSTANCE),
        state.get("new_instance_class", FIRST_CLASS),
    )
    state["embedder"] = DistinctEmbedder()
    stand_in_for_the_provider(state, monkeypatch)
    run_command(state, command.replace("onto ", ""))


# Then: what the command wrote

@then(parsers.re(r'the exit code is (?P<code>\d+)'))
def step_then_exit_code_is(state: dict, code: str) -> None:
    assert state["exit_code"] == int(code), (state["exit_code"], state["stderr"])


@then("the exit code is non-zero")
def step_then_exit_code_is_non_zero(state: dict) -> None:
    assert state["exit_code"] != 0, state["stdout"]


@then("the error message explains the required arguments")
def step_then_error_explains_required_arguments(state: dict) -> None:
    message = state["stderr"] + state["stdout"]
    for argument in ("--config", "--input", "--output"):
        assert argument in message, f"{argument} is not mentioned in: {message}"


@then("the help lists the commands build and update")
def step_then_help_lists_the_commands(state: dict) -> None:
    for command in ("build", "update"):
        assert command in state["stdout"], f"{command} is missing from: {state['stdout']}"


@then(parsers.re(r'the files (?P<names>.+) exist'))
def step_then_files_exist(workdir: Path, names: str) -> None:
    for name in names.split(","):
        path = workdir / name.strip().strip('"')
        assert path.exists(), f"{path} was not written"


@then(parsers.re(rf'the ontology in {quoted("name")} has been extended'))
def step_then_ontology_extended(workdir: Path, name: str) -> None:
    """The class of the earlier build is still there, the new one joined it, and the instance
    the earlier build wrote is untouched next to the one the new document brought."""
    output_dir = workdir / name
    classes = read_yaml(output_dir / SCHEMA_FILE_NAME)["classes"]
    assert set(classes) == {FIRST_CLASS, SECOND_CLASS}, sorted(classes)
    instances = read_yaml(output_dir / INSTANCES_FILE)["instances"]
    assert EXISTING_INSTANCE in instances, sorted(instances)
    # an instance is written as a single token, so the name the model proposed is looked up
    # in the form the build stores it
    assert NEW_INSTANCE.replace(" ", "_") in instances, sorted(instances)
