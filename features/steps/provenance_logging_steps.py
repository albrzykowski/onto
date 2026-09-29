import json
import re
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from features.steps.support import log_events, log_lines, quoted, word
from onto.chunking import chunk_document
from onto.config import BuilderConfig
from onto.ingestion import Document, compute_fingerprint
from onto.provenance import ProvenanceLog, SourceRef

REQUIRED_FIELDS = {"event", "id", "source_documents", "source_excerpt", "timestamp", "mode"}

TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def source_ref_from_chunk(chunk: str) -> SourceRef:
    """A `<path>#c<N>` chunk id names its own path, so the path is read off it."""
    return SourceRef(path=Path(chunk.rpartition("#")[0]), chunk_id=chunk)


def assert_build_mode(state: dict, mode: str) -> None:
    """The feature asserts the build mode only in the creation scenario, so the
    update scenarios would otherwise never check that the log is stamped."""
    stamped = {entry["mode"] for entry in log_events(state["log_path"])}
    assert stamped == {mode}, f"log is stamped {stamped}, expected {mode}"


def write_records(state: dict, path: Path, mode: str) -> None:
    """Stand in for a build: record everything the extraction produced."""
    log = ProvenanceLog(path, mode)
    for record in state["records"]:
        log.record(**record)
    state["log_path"] = path
    assert_build_mode(state, mode)


def find_event(state: dict, name: str) -> dict:
    entries = log_events(state["log_path"])
    names = [entry["event"] for entry in entries]
    assert name in names, f"no {name} event in the log: {names}"
    return next(entry for entry in entries if entry["event"] == name)


def latest_event(state: dict) -> dict:
    return log_events(state["log_path"])[-1]


def document_built_from(text: str, path: str) -> SourceRef:
    """Chunk a document for real, so the log carries a real chunk identifier."""
    document = Document(path=Path(path), text=text, fingerprint=compute_fingerprint(text))
    chunk = chunk_document(document, BuilderConfig())[0]
    return SourceRef(path=chunk.source_path, chunk_id=chunk.chunk_id)


# Given: what the language model returns

@given(
    parsers.re(
        rf'the LLM returns the class {word("id")} derived from the sentence '
        rf'{quoted("excerpt")} in chunk {quoted("chunk")}'
    )
)
def step_given_llm_returns_class(state: dict, id: str, excerpt: str, chunk: str) -> None:
    state["records"].append(
        {
            "event": "class.created",
            "id": id,
            "source_excerpt": excerpt,
            "source_documents": [source_ref_from_chunk(chunk)],
        }
    )


@given(
    parsers.re(
        rf'the existing class {word("id")} is updated in update mode by merging '
        rf'the concept {quoted("merged")}'
    )
)
def step_given_class_updated_by_merging(state: dict, id: str, merged: str) -> None:
    excerpt = f"The text states that {merged} is another name for {id}."
    state["merged_source"] = "corpus/article2.txt#c1"
    state["updated_source"] = "corpus/article3.txt#c2"
    state["records"].extend(
        [
            {
                "event": "class.merged",
                "id": id,
                "source_excerpt": excerpt,
                "source_documents": [source_ref_from_chunk(state["merged_source"])],
                "merged_ids": [merged],
            },
            {
                "event": "class.updated",
                "id": id,
                "source_excerpt": excerpt,
                "source_documents": [source_ref_from_chunk(state["updated_source"])],
            },
        ]
    )


@given(
    parsers.re(
        rf'a candidate class {word("id")} is rejected because it is not in allowed_classes'
    )
)
def step_given_candidate_rejected(state: dict, id: str) -> None:
    state["records"].append(
        {
            "event": "class.rejected",
            "id": id,
            "reason": "not_in_allowed_classes",
        }
    )


@given(parsers.re(r"an ontology built from (?P<count>\d+) documents"))
def step_given_ontology_built_from_documents(
    state: dict, count: str, provenance_path: Path
) -> None:
    for number in range(1, int(count) + 1):
        text = f"A combustion engine converts energy into motion, in document {number}."
        state["records"].append(
            {
                "event": "class.created",
                "id": f"Engine{number}",
                "source_excerpt": text,
                "source_documents": [document_built_from(text, f"corpus/article{number}.txt")],
            }
        )
    write_records(state, provenance_path, "override")


@given("an unchanged document in update mode")
def step_given_unchanged_document(state: dict) -> None:
    state["document_path"] = "corpus/article1.txt"
    state["records"].append(
        {
            "event": "document.skipped",
            "id": state["document_path"],
            "reason": "unchanged_fingerprint",
        }
    )


# When

@when("the ontology is built")
def step_when_ontology_is_built(state: dict, provenance_path: Path) -> None:
    write_records(state, provenance_path, "override")


@when("the ontology is updated")
def step_when_ontology_is_updated(state: dict, provenance_path: Path) -> None:
    write_records(state, provenance_path, "update")


# Then: class creation

@then(parsers.re(rf'the provenance\.jsonl contains a {quoted("name")} event'))
def step_then_provenance_contains_event(state: dict, name: str) -> None:
    find_event(state, name)


@then(parsers.re(rf'the event has the id {quoted("id")}'))
def step_then_event_has_id(state: dict, id: str) -> None:
    assert latest_event(state)["id"] == id


@then(
    parsers.re(
        rf'the event has source_documents with the path {quoted("path")} '
        rf'and the chunk {quoted("chunk")}'
    )
)
def step_then_event_source_documents(state: dict, path: str, chunk: str) -> None:
    source = latest_event(state)["source_documents"][0]
    assert source["path"] == path
    assert source["chunk_id"].endswith(f"#{chunk}")


@then(parsers.re(rf'the event has a source_excerpt equal to {quoted("excerpt")}'))
def step_then_event_source_excerpt(state: dict, excerpt: str) -> None:
    assert latest_event(state)["source_excerpt"] == excerpt


@then("the event has a timestamp and the build mode")
def step_then_event_has_timestamp_and_mode(state: dict) -> None:
    entry = latest_event(state)
    assert TIMESTAMP_PATTERN.fullmatch(entry["timestamp"]), entry["timestamp"]
    assert entry["mode"] == "override"


# Then: merge and update

@then(
    parsers.re(
        rf'the log contains a {quoted("name")} event naming the surviving concept '
        rf'{word("id")} and the merged concept {word("merged")}, with the source text excerpt'
    )
)
def step_then_merged_event(state: dict, name: str, id: str, merged: str) -> None:
    entry = find_event(state, name)
    assert entry["id"] == id
    assert merged in entry["merged_ids"]
    assert entry["source_excerpt"]


@then(parsers.re(rf'the log contains a {quoted("name")} event with the new source document'))
def step_then_updated_event_with_new_source(state: dict, name: str) -> None:
    chunk = find_event(state, name)["source_documents"][0]["chunk_id"]
    assert chunk == state["updated_source"]
    assert chunk != state["merged_source"]


# Then: rejections and skipped documents

@then(parsers.re(rf'the log contains a {quoted("name")} event with the reason {quoted("reason")}'))
def step_then_event_with_reason(state: dict, name: str, reason: str) -> None:
    assert find_event(state, name)["reason"] == reason


@then(
    parsers.re(
        rf'the log contains a {quoted("name")} event with the document path and the reason '
        rf'{quoted("reason")}'
    )
)
def step_then_skipped_document_with_reason(state: dict, name: str, reason: str) -> None:
    entry = find_event(state, name)
    assert entry["id"] == state["document_path"]
    assert entry["reason"] == reason


# Then: the log as a whole

@then("every line of provenance.jsonl parses as a JSON object")
def step_then_every_line_is_a_json_object(state: dict) -> None:
    for line in log_lines(state["log_path"]):
        assert isinstance(json.loads(line), dict)


@then("every entry has the fields event, id, source_documents, source_excerpt, timestamp, mode")
def step_then_entries_have_required_fields(state: dict) -> None:
    for entry in log_events(state["log_path"]):
        assert entry.keys() >= REQUIRED_FIELDS, sorted(entry)
