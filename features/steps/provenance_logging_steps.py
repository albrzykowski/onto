"""Step definitions for the provenance log.

Every scenario in this feature runs a real `onto.builder.build`, so what the log is asserted
against is what the pipeline wrote rather than what a step put there itself: an event in this
log exists because the builder recorded it while writing a schema or an instance.
"""

import json
import math
import re
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from features.steps.support import FakeLLM, log_events, quoted, valid_config, word
from onto.builder import PROVENANCE_FILE_NAME, STATE_FILE_NAME, build
from onto.ingestion import compute_fingerprint

REQUIRED_FIELDS = {"event", "id", "source_documents", "source_excerpt", "timestamp", "mode"}

TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

CORPUS = "corpus"

# a window the length of one sentence, so a document stating the sentence three times is cut
# into exactly three chunks and a scenario can name the one it means
SENTENCE_WINDOW = 12

SENTENCE = "VW has been producing the Golf, a compact passenger car, since 1974."

SURVIVING = "Vehicle"
MERGED = "Car"
NOT_ALLOWED = "Person"

OLD_DOCUMENT = "old.txt"
NEW_DOCUMENT = "new.txt"

MERGED_SOURCE = f"{CORPUS}/{NEW_DOCUMENT}#c1"
UPDATED_SOURCE = f"{CORPUS}/{NEW_DOCUMENT}#c3"

MERGE_MARKER = "denote the same concept"

# above the default similarity_threshold of 0.85, or the pair is never put to the model
RESEMBLANCE = 0.95


def described(name: str) -> str:
    return f"A {name} as the corpus describes it."


def narrow_config(**overrides: object):
    """A configuration whose chunks are single sentences, so a scenario can say which chunk a
    concept was read from."""
    return valid_config(max_chunk_tokens=SENTENCE_WINDOW, overlap_tokens=0, **overrides)


def write_document(workdir: Path, name: str, text: str) -> None:
    corpus = workdir / CORPUS
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / name).write_text(text, encoding="utf-8")


def chunk_markers(prompt: str) -> list[str]:
    """The chunk identifiers the prompt shows the model.

    A feature names a chunk relative to the corpus while the prompt shows the path the build
    was pointed at, so a reply is matched on the name ending the marker rather than on the
    whole string.
    """
    return re.findall(r"\[([^\]\s]+#c\d+)\]", prompt)


def client_for(
    classes_by_chunk: dict[str, list[str]] | None = None,
    *,
    excerpt: str = SENTENCE,
    merge_verified: bool = False,
) -> FakeLLM:
    """A build asks the model three things; the double answers each by what the prompt asks for,
    so no scenario depends on the order the calls happen to come in.

    `classes_by_chunk` says which class the extractor finds in which chunk, which is what ties a
    class to the text it was read from, and those same classes are what the planner describes.
    """
    proposed = [name for names in (classes_by_chunk or {}).values() for name in names]

    def concepts(prompt: str) -> str:
        names = [
            name
            for marker in chunk_markers(prompt)
            for chunk, found in (classes_by_chunk or {}).items()
            if marker.endswith(chunk)
            for name in found
        ]
        return json.dumps(
            {"classes": [{"name": name, "excerpt": excerpt} for name in names], "relations": []}
        )

    def plan(_prompt: str) -> str:
        return json.dumps(
            {"classes": {name: {"description": described(name), "slots": []} for name in proposed}}
        )

    def respond(call: int) -> str:
        prompt = client.prompts[call]
        if MERGE_MARKER in prompt:
            return json.dumps({"same_concept": merge_verified})
        if "Candidate classes:" in prompt or "New concepts:" in prompt:
            return plan(prompt)
        if "Classes of the schema:" in prompt:
            return json.dumps({"instances": []})
        return concepts(prompt)

    client = FakeLLM(respond)
    return client


class ResemblingEmbedder:
    """Vectors reproducing one stated resemblance and nothing else: every text gets an axis of
    its own, so two texts given no resemblance are orthogonal, and the one pair that should
    resemble leans onto the other's axis at the stated strength."""

    def __init__(self, resemblances: dict[str, tuple[str, float]]) -> None:
        self._resemblances = resemblances

    def embed(self, texts: list[str]) -> list[list[float]]:
        # one axis per distinct text, so a name that appears twice in one call keeps the same
        # vector both times
        distinct = list(dict.fromkeys(texts))
        axis = {text: index for index, text in enumerate(distinct)}
        vectors = [[0.0] * len(distinct) for _ in distinct]
        for index in range(len(distinct)):
            vectors[index][index] = 1.0
        for text, (other, score) in self._resemblances.items():
            if text not in axis or other not in axis:
                continue
            vectors[axis[text]] = [0.0] * len(distinct)
            vectors[axis[text]][axis[text]] = math.sqrt(max(0.0, 1 - score**2))
            vectors[axis[text]][axis[other]] = score
        return [vectors[axis[text]] for text in texts]


def run_build(
    state: dict,
    workdir: Path,
    output_dir: Path,
    client: FakeLLM,
    *,
    config=None,
    embedder=None,
) -> None:
    """Run one build the way a caller would: the documents on disk, the configuration the
    scenario arranged, and no stand-in for anything but the model."""
    state["provenance_path"] = output_dir / PROVENANCE_FILE_NAME
    build(
        input_dir=workdir / CORPUS,
        output_dir=output_dir,
        config=config or state["config"],
        llm=client,
        embedder=embedder,
    )


def find_event(state: dict, name: str) -> dict:
    entries = log_events(state["provenance_path"])
    names = [entry["event"] for entry in entries]
    assert name in names, f"no {name} event in the log: {names}"
    state["checked_event"] = next(entry for entry in entries if entry["event"] == name)
    return state["checked_event"]


def checked_event(state: dict) -> dict:
    return state["checked_event"]


# Given: the corpus and what the model finds in it

@given(
    parsers.re(
        rf'the LLM returns the class {word("id")} derived from the sentence '
        rf'{quoted("excerpt")} in chunk {quoted("chunk")}'
    )
)
def step_given_llm_returns_class(
    state: dict, workdir: Path, id: str, excerpt: str, chunk: str
) -> None:
    # the sentence stated three times is three chunks of one sentence each, so the chunk the
    # scenario names really does hold the text it attributes to that chunk
    name = chunk.rpartition("#")[0].rpartition("/")[2]
    write_document(workdir, name, " ".join([excerpt] * 3))
    state["config"] = narrow_config(mode="override")
    state["classes_by_chunk"] = {chunk: [id]}
    state["excerpt"] = excerpt


@given(
    parsers.re(
        rf'the existing class {word("id")} is updated in update mode by merging '
        rf'the concept {quoted("merged")}'
    )
)
def step_given_class_updated_by_merging(
    state: dict, workdir: Path, output_dir: Path, id: str, merged: str
) -> None:
    """A first build writes the class, and the update then names it a second time alongside a
    second word for it: the word joins the class the schema already has, and the class itself
    is cited once more.

    The second document is written after the first build, so the state records only the first
    and the update has this document alone to read.
    """
    write_document(workdir, OLD_DOCUMENT, SENTENCE)
    state["config"] = narrow_config(mode="update")
    run_build(
        state,
        workdir,
        output_dir,
        client_for({f"{CORPUS}/{OLD_DOCUMENT}#c1": [id]}),
        config=narrow_config(mode="override"),
    )
    write_document(workdir, NEW_DOCUMENT, " ".join([SENTENCE] * 3))
    state["classes_by_chunk"] = {MERGED_SOURCE: [merged], UPDATED_SOURCE: [id]}


@given(
    parsers.re(rf'a candidate class {word("id")} is rejected because it is not in allowed_classes')
)
def step_given_candidate_rejected(state: dict, workdir: Path, id: str) -> None:
    """The configuration allows one class and the corpus states another, which is the only way a
    class the model proposes can fall outside an allow-list."""
    write_document(workdir, NEW_DOCUMENT, SENTENCE)
    state["config"] = narrow_config(
        mode="override", allowed_classes={SURVIVING: described(SURVIVING)}
    )
    state["classes_by_chunk"] = {f"{CORPUS}/{NEW_DOCUMENT}#c1": [id]}


@given(parsers.re(r"an ontology built from (?P<count>\d+) documents"))
def step_given_ontology_built_from_documents(
    state: dict, workdir: Path, output_dir: Path, count: str
) -> None:
    found = {}
    for number in range(1, int(count) + 1):
        write_document(workdir, f"article{number}.txt", f"{SENTENCE} Document {number}.")
        found[f"{CORPUS}/article{number}.txt#c1"] = [f"Concept{number}"]
    state["config"] = valid_config(mode="override")
    state["classes_by_chunk"] = found
    run_build(state, workdir, output_dir, client_for(found))


@given("an unchanged document in update mode")
def step_given_unchanged_document(state: dict, workdir: Path, output_dir: Path) -> None:
    """The state already records the document under its own fingerprint, so an update has
    nothing left to read. The state keys a document by its name inside the corpus."""
    write_document(workdir, OLD_DOCUMENT, SENTENCE)
    state["config"] = valid_config(mode="update")
    state["classes_by_chunk"] = {}
    state["document_path"] = OLD_DOCUMENT
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / STATE_FILE_NAME).write_text(
        json.dumps({OLD_DOCUMENT: compute_fingerprint(SENTENCE)}) + "\n", encoding="utf-8"
    )


# When

@when("the ontology is built")
def step_when_ontology_is_built(state: dict, workdir: Path, output_dir: Path) -> None:
    run_build(
        state,
        workdir,
        output_dir,
        client_for(state["classes_by_chunk"], excerpt=state.get("excerpt", SENTENCE)),
    )


@when("the ontology is updated")
def step_when_ontology_is_updated(state: dict, workdir: Path, output_dir: Path) -> None:
    run_build(
        state,
        workdir,
        output_dir,
        client_for(state["classes_by_chunk"], merge_verified=True),
        embedder=ResemblingEmbedder({MERGED: (SURVIVING, RESEMBLANCE)}),
    )


# Then: class creation

@then(parsers.re(rf'the provenance\.jsonl contains a {quoted("name")} event'))
def step_then_provenance_contains_event(state: dict, name: str) -> None:
    find_event(state, name)


@then(parsers.re(rf'the event has the id {quoted("id")}'))
def step_then_event_has_id(state: dict, id: str) -> None:
    assert checked_event(state)["id"] == id


@then(
    parsers.re(
        rf'the event has source_documents with the path {quoted("path")} '
        rf'and the chunk {quoted("chunk")}'
    )
)
def step_then_event_source_documents(state: dict, path: str, chunk: str) -> None:
    source = checked_event(state)["source_documents"][0]
    assert source["path"].endswith(path)
    assert source["chunk_id"].endswith(f"#{chunk}")


@then(parsers.re(rf'the event has a source_excerpt equal to {quoted("excerpt")}'))
def step_then_event_source_excerpt(state: dict, excerpt: str) -> None:
    assert checked_event(state)["source_excerpt"] == excerpt


@then("the event has a timestamp and the build mode")
def step_then_event_has_timestamp_and_mode(state: dict) -> None:
    entry = checked_event(state)
    assert TIMESTAMP_PATTERN.fullmatch(entry["timestamp"]), entry["timestamp"]
    assert entry["mode"] == "override", entry["mode"]


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
    assert chunk.endswith(UPDATED_SOURCE), chunk
    assert chunk != MERGED_SOURCE


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
    assert entry["id"] == state["document_path"], entry["id"]
    assert entry["reason"] == reason


# Then: the log as a whole

@then("every line of provenance.jsonl parses as a JSON object")
def step_then_every_line_is_a_json_object(state: dict) -> None:
    text = state["provenance_path"].read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip():
            assert isinstance(json.loads(line), dict)


@then("every entry has the fields event, id, source_documents, source_excerpt, timestamp, mode")
def step_then_entries_have_required_fields(state: dict) -> None:
    for entry in log_events(state["provenance_path"]):
        assert entry.keys() >= REQUIRED_FIELDS, sorted(entry)
