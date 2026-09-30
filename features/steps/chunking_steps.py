import re
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from features.steps.support import quoted, valid_config
from onto.chunking import chunk_document, tokenize
from onto.ingestion import Document, compute_fingerprint

DOCUMENT_PATH = Path("corpus/article1.txt")


def make_document(token_count: int) -> Document:
    text = " ".join(f"token{index}" for index in range(token_count))
    return Document(path=DOCUMENT_PATH, text=text, fingerprint=compute_fingerprint(text))


def perform_chunking(state: dict) -> None:
    state["chunks"] = chunk_document(state["document"], state["config"])


def overlap_length(left: list[str], right: list[str]) -> int:
    """Longest suffix of left that is also a prefix of right."""
    for size in range(min(len(left), len(right)), 0, -1):
        if left[-size:] == right[:size]:
            return size
    return 0


# Given: chunking configuration (Background)

@given(parsers.re(rf'a configuration with chunking.strategy {quoted("strategy")}'))
def step_given_chunking_strategy(state: dict, strategy: str):
    state["config"] = valid_config(chunking_strategy=strategy)


@given(parsers.re(r"max_chunk_tokens (?P<value>\d+)"))
def step_given_max_chunk_tokens(state: dict, value: str):
    state["config"].max_chunk_tokens = int(value)


@given(parsers.re(r"overlap_tokens (?P<value>\d+)"))
def step_given_overlap_tokens(state: dict, value: str):
    state["config"].overlap_tokens = int(value)


# Given: documents

@given(parsers.re(r"a document with (?P<count>\d+) tokens of text"))
def step_given_document_with_tokens(state: dict, count: str):
    state["document"] = make_document(int(count))


@given("any document split into chunks")
def step_given_document_split_into_chunks(state: dict):
    state["document"] = make_document(250)
    perform_chunking(state)


# When

@when("chunking is performed")
def step_when_chunking_is_performed(state: dict):
    perform_chunking(state)


# Then

@then("the number of chunks is greater than 1")
def step_then_multiple_chunks(state: dict):
    assert len(state["chunks"]) > 1


@then("the number of chunks is 1")
def step_then_single_chunk(state: dict):
    assert len(state["chunks"]) == 1


@then(parsers.re(r"every chunk has at most (?P<limit>\d+) tokens"))
def step_then_every_chunk_within_token_limit(state: dict, limit: str):
    maximum = int(limit)
    for chunk in state["chunks"]:
        assert len(tokenize(chunk.text)) <= maximum, f"{chunk.chunk_id} is too long"


@then(parsers.re(rf"every chunk has the identifier {quoted('template')}"))
def step_then_every_chunk_has_identifier(state: dict, template: str):
    concrete = template.replace("<path>", str(state["document"].path))
    parts = [r"\d+" if part == "<N>" else re.escape(part) for part in re.split(r"(<N>)", concrete)]
    pattern = re.compile("^" + "".join(parts) + "$")

    identifiers = [chunk.chunk_id for chunk in state["chunks"]]
    for identifier in identifiers:
        assert pattern.match(identifier), f"{identifier!r} does not match {template!r}"

    assert len(set(identifiers)) == len(identifiers), "chunk identifiers are not unique"
    assert identifiers == [
        f"{state['document'].path}#c{index}" for index in range(1, len(identifiers) + 1)
    ]


@then(
    parsers.re(
        r"the tail of chunk N overlaps the head of chunk N\+1 by at least (?P<minimum>\d+) tokens"
    )
)
def step_then_adjacent_chunks_overlap(state: dict, minimum: str):
    chunks = [tokenize(chunk.text) for chunk in state["chunks"]]
    assert len(chunks) > 1, "overlap needs at least two chunks"

    for index, (left, right) in enumerate(zip(chunks, chunks[1:], strict=False), start=1):
        actual = overlap_length(left, right)
        assert actual >= int(minimum), (
            f"chunk {index} and {index + 1} share only {actual} tokens, expected {minimum}"
        )


@then('every chunk has a "source_path" attribute pointing to its source document')
def step_then_every_chunk_has_source_path(state: dict):
    assert state["chunks"]
    for chunk in state["chunks"]:
        assert chunk.source_path == state["document"].path
