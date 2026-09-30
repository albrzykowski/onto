import json
import logging
import re
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from features.steps.support import FakeLLM, described, quoted, split_names, valid_config
from onto.chunking import Chunk, chunk_document
from onto.config import BuilderConfig
from onto.extraction import extract
from onto.ingestion import Document, compute_fingerprint
from onto.llm import LLMError

DEFAULT_CHUNK_TEXT = "The 1.6 TDI engine is installed in the Golf produced by VW"
POLISH_CHUNK_TEXT = "Silnik TDI 1.6 jest montowany w Golfie produkowanym przez VW."

ENGLISH_CLASSES = ["engine", "vehicle", "engine type"]
ENGLISH_RELATIONS = ["Has Engine", "ProducedBy"]

DEFAULT_REPLY = json.dumps(
    {
        "classes": [
            {"name": "Vehicle", "excerpt": DEFAULT_CHUNK_TEXT},
            {"name": "Engine", "excerpt": DEFAULT_CHUNK_TEXT},
        ],
        "relations": [{"name": "has_engine", "excerpt": DEFAULT_CHUNK_TEXT}],
    }
)

SCOPE_MARKER = "Scope of the ontology:"
CONSTRAINED_MARKER = "only these concepts and nothing else"
RELEVANCE_MARKER = "relevant to"
PREDEFINED_MARKERS = ("Predefined classes:", "Predefined relations:")

PASCAL_CASE = re.compile(r"[A-Z][A-Za-z0-9]*")
SNAKE_CASE = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)*")


def make_chunk(number: int, text: str) -> Chunk:
    path = Path(f"corpus/article{number}.txt")
    document = Document(path=path, text=text, fingerprint=compute_fingerprint(text))
    return chunk_document(document, valid_config())[0]


def config_for(state: dict) -> BuilderConfig:
    if state["config"] is None:
        state["config"] = valid_config()
    return state["config"]


def current_text(state: dict) -> str:
    return state["chunks"][0].text


def add_chunks(state: dict, count: int) -> None:
    for number in range(1, count + 1):
        state["chunks"].append(make_chunk(number, f"Document {number} describes an engine."))


def reply_for(classes: list[str], relations: list[str], excerpt: str) -> str:
    return json.dumps(
        {
            "classes": [{"name": name, "excerpt": excerpt} for name in classes],
            "relations": [{"name": name, "excerpt": excerpt} for name in relations],
        }
    )


def client_for(state: dict) -> FakeLLM:
    def respond(call: int) -> str:
        if call == state.get("failing_call"):
            raise LLMError("the model is overloaded")
        return state.get("reply", DEFAULT_REPLY)

    return FakeLLM(respond)


def chunks_for(state: dict) -> list[Chunk]:
    """Scenarios that only assert on the prompt register no chunks, so they get one."""
    return state["chunks"] or [make_chunk(1, DEFAULT_CHUNK_TEXT)]


def only_prompt(state: dict) -> str:
    prompts = state["llm"].prompts
    assert len(prompts) == 1, f"expected a single LLM call, got {len(prompts)}"
    return prompts[0]


def class_names(state: dict) -> list[str]:
    return [c.name for c in state["candidates"] if c.kind == "class"]


def relation_names(state: dict) -> list[str]:
    return [c.name for c in state["candidates"] if c.kind == "relation"]


def perform_extraction(state: dict) -> None:
    state["llm"] = client_for(state)
    state["candidates"] = extract(chunks_for(state), config_for(state), state["llm"])


# Given: the text

@given(parsers.re(rf'a chunk with the text {quoted("text")}'))
def step_given_chunk_with_text(state: dict, text: str) -> None:
    state["chunks"].append(make_chunk(1, text))


@given("a chunk in Polish containing domain concepts")
def step_given_chunk_in_polish(state: dict) -> None:
    state["chunks"].append(make_chunk(1, POLISH_CHUNK_TEXT))


# Given: what the LLM returns

@given(
    parsers.re(
        r"the LLM returns the candidates (?P<classes>[\w, ]+?) "
        r"and the relations (?P<relations>[\w, ]+?)(?:, fenced in a markdown code block)?\s*$"
    )
)
def step_given_llm_returns_candidates(state: dict, classes: str, relations: str) -> None:
    state["reply"] = reply_for(split_names(classes), split_names(relations), current_text(state))


@given("the LLM returns candidates with English names")
def step_given_llm_returns_english_names(state: dict) -> None:
    state["reply"] = reply_for(ENGLISH_CLASSES, ENGLISH_RELATIONS, current_text(state))


@given("the LLM fails for the first chunk")
def step_given_llm_fails_for_first_chunk(state: dict) -> None:
    state["failing_call"] = 0


# Given: configuration

@given(
    parsers.re(
        rf'a configuration with the domain {quoted("domain")} described as {quoted("description")}'
    )
)
def step_given_configuration_with_domain(state: dict, domain: str, description: str) -> None:
    config_for(state).domains = {domain: description}


@given(parsers.re(r'allowed_classes describing (?P<names>.+)$'))
def step_given_allowed_classes_describing(state: dict, names: str) -> None:
    config_for(state).allowed_classes = described(names)


@given(parsers.re(r'allowed_relations describing (?P<names>.+)$'))
def step_given_allowed_relations_describing(state: dict, names: str) -> None:
    config_for(state).allowed_relations = described(names)


@given("empty allowed_classes and allowed_relations")
def step_given_empty_allow_lists(state: dict) -> None:
    config_for(state).allowed_classes = {}
    config_for(state).allowed_relations = {}


@given(parsers.re(r"a configuration with batch_size (?P<size>\d+)"))
def step_given_batch_size(state: dict, size: str) -> None:
    config_for(state).batch_size = int(size)


# Given: how much to process

@given(parsers.re(r"(?P<count>\d+) chunks to process"))
def step_given_chunks_to_process(state: dict, count: str) -> None:
    add_chunks(state, int(count))


@given(parsers.re(r"(?P<count>\d+) chunks\s*$"))
def step_given_chunks(state: dict, count: str) -> None:
    add_chunks(state, int(count))


# When

@when(parsers.re(r"extraction is performed for (?:the|all) chunks?"))
def step_when_extraction_is_performed(state: dict) -> None:
    perform_extraction(state)


@when("extraction is performed")
def step_when_extraction_is_performed_without_a_target(state: dict) -> None:
    perform_extraction(state)


# Then: candidates

@then(parsers.re(r"the result contains the class candidates (?P<names>[\w, ]+?)\s*$"))
def step_then_result_contains_classes(state: dict, names: str) -> None:
    found = class_names(state)
    for name in split_names(names):
        assert name in found, f"{name} missing from {found}"


@then(parsers.re(r"the result contains the relation candidates (?P<names>[\w, ]+?)\s*$"))
def step_then_result_contains_relations(state: dict, names: str) -> None:
    found = relation_names(state)
    for name in split_names(names):
        assert name in found, f"{name} missing from {found}"


@then('every candidate carries a "source_documents" reference with the chunk identifier')
def step_then_candidates_carry_source_documents(state: dict) -> None:
    expected = state["chunks"][0].chunk_id
    for candidate in state["candidates"]:
        assert any(ref.chunk_id == expected for ref in candidate.source_documents), (
            f"{candidate.name} does not cite {expected}"
        )


@then('every candidate carries the text excerpt it was derived from')
def step_then_candidates_carry_excerpt(state: dict) -> None:
    expected = state["chunks"][0].text
    for candidate in state["candidates"]:
        assert candidate.source_excerpt == expected, candidate.name


@then("every class candidate has a PascalCase name")
def step_then_class_names_are_pascal_case(state: dict) -> None:
    for name in class_names(state):
        assert PASCAL_CASE.fullmatch(name), f"{name!r} is not PascalCase"


@then("every relation candidate has a snake_case name")
def step_then_relation_names_are_snake_case(state: dict) -> None:
    for name in relation_names(state):
        assert SNAKE_CASE.fullmatch(name), f"{name!r} is not snake_case"


@then(
    parsers.re(r"the LLM prompt states a limit of (?P<limit>\d+) classes and (?P=limit) relations")
)
def step_then_prompt_states_concept_limit(state: dict, limit: str) -> None:
    prompt = only_prompt(state)
    assert f"At most {limit} classes and at most {limit} relations" in prompt

@then(
    parsers.re(
        r"the LLM prompt lists the domains and the predefined classes (?P<names>[\w, ]+?)\s*$"
    )
)
def step_then_prompt_lists_domains_and_classes(state: dict, names: str) -> None:
    prompt = only_prompt(state)
    for domain, description in config_for(state).domains.items():
        assert domain in prompt, f"{domain} missing from the prompt"
        assert description in prompt, f"description of {domain} missing from the prompt"
    for name in split_names(names):
        assert name in prompt, f"{name} missing from the prompt"


@then(parsers.re(r"the LLM prompt lists the predefined relation (?P<name>[\w_]+)"))
def step_then_prompt_lists_relation(state: dict, name: str) -> None:
    assert name in only_prompt(state), f"{name} missing from the prompt"


@then("the prompt instructs the LLM to return only these concepts and nothing else")
def step_then_prompt_forbids_new_concepts(state: dict) -> None:
    assert CONSTRAINED_MARKER in only_prompt(state)


@then("the LLM prompt contains the domain name and its description")
def step_then_prompt_contains_domain_description(state: dict) -> None:
    prompt = only_prompt(state)
    for domain, description in config_for(state).domains.items():
        assert domain in prompt, f"{domain} missing from the prompt"
        assert description in prompt, f"description of {domain} missing from the prompt"


@then(
    parsers.re(
        r"the prompt instructs the LLM to extract concepts relevant to the "
        r"(?P<domain>[\w]+) domain"
    )
)
def step_then_prompt_scopes_to_domain(state: dict, domain: str) -> None:
    prompt = only_prompt(state)
    assert RELEVANCE_MARKER in prompt, "the prompt does not ask for domain relevance"
    assert domain in prompt, f"{domain} missing from the prompt"


@then("the LLM prompt does not constrain the set of concepts")
def step_then_prompt_is_unconstrained(state: dict) -> None:
    prompt = only_prompt(state)
    for marker in (SCOPE_MARKER, *PREDEFINED_MARKERS, RELEVANCE_MARKER):
        assert marker not in prompt, f"the prompt is constrained by {marker!r}"


# Then: the LLM's own answer

@then(
    parsers.re(
        r"the LLM returns exactly the classes (?P<classes>[\w, ]+?) "
        r"and the relation (?P<relations>[\w, ]+?)\s*$"
    )
)
def step_then_llm_returns_exact_concepts(state: dict, classes: str, relations: str) -> None:
    assert set(class_names(state)) == set(split_names(classes))
    assert set(relation_names(state)) == set(split_names(relations))


@then(parsers.re(r"the LLM returns only \w+ concepts such as (?P<name>\w+)"))
def step_then_llm_returns_domain_concepts(state: dict, name: str) -> None:
    assert name in class_names(state), f"{name} missing from the result"


@then(parsers.re(r"the LLM is called exactly (?P<count>\d+) times \(batches of [\d, ]+\)"))
def step_then_llm_called_batched_times(state: dict, count: str) -> None:
    calls = len(state["llm"].prompts)
    assert calls == int(count), f"the LLM was called {calls} times"


# Then: failures

@then("the result contains candidates from the second chunk")
def step_then_result_contains_second_chunk(state: dict) -> None:
    expected = state["chunks"][1].chunk_id
    assert any(
        ref.chunk_id == expected
        for candidate in state["candidates"]
        for ref in candidate.source_documents
    ), f"no candidate cites {expected}"


@then("an error for the first chunk is logged")
def step_then_error_logged_for_first_chunk(
    state: dict, caplog: pytest.LogCaptureFixture
) -> None:
    errors = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    expected = state["chunks"][0].chunk_id
    assert any(expected in message for message in errors), f"no error about {expected}: {errors}"
