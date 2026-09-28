import hashlib
import logging
import re
from pathlib import Path

import pytest
from docx import Document as DocxDocument
from pytest_bdd import given, parsers, then, when

from onto.ingestion import NoDocumentsFoundError, load_documents

SAMPLE_TEXT = "A combustion engine converts chemical energy into mechanical motion."

FILE_NAME = r'"([^"]+)"'
FILE_LIST = r'"[^"]+"(?:\s*(?:,|and)\s*"[^"]+")*'


def quoted(group: str) -> str:
    return rf'"(?P<{group}>[^"]+)"'


def build_pdf(text: str) -> bytes:
    """Assemble a minimal single-page PDF carrying the given text."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(bodies) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += (
        f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(pdf)


def create_file(path: Path) -> None:
    """Create a file of the format implied by its suffix."""
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        path.write_bytes(build_pdf(SAMPLE_TEXT))
    elif suffix == ".docx":
        docx = DocxDocument()
        docx.add_paragraph(SAMPLE_TEXT)
        docx.save(str(path))
    elif suffix in {".txt", ".md"}:
        path.write_text(SAMPLE_TEXT, encoding="utf-8")
    else:
        path.write_bytes(b"\x89PNG\r\n\x1a\n not a real image")


def create_directory(workdir: Path, name: str) -> Path:
    path = workdir / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def loaded_documents(state: dict) -> list:
    assert state["error"] is None, f"ingestion failed: {state['error']!r}"
    return state["documents"]


def logged_messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno == level]


# Given: input directories

@given(parsers.re(rf'an empty input directory {quoted("name")}'))
def step_given_empty_input_directory(workdir: Path, name: str):
    create_directory(workdir, name)


@given(parsers.re(rf'an input directory {quoted("name")} without files'))
def step_given_input_directory_without_files(workdir: Path, name: str):
    create_directory(workdir, name)


# Given: documents

@given(parsers.re(rf'files (?P<names>{FILE_LIST}) in the directory {quoted("directory")}'))
def step_given_files(workdir: Path, names: str, directory: str):
    for name in re.findall(FILE_NAME, names):
        create_file(workdir / directory / name)


@given(parsers.re(rf'a file {quoted("name")} in the directory {quoted("directory")}'))
def step_given_file(workdir: Path, name: str, directory: str):
    create_file(workdir / directory / name)


@given(parsers.re(rf'a corrupted file {quoted("name")} in the directory {quoted("directory")}'))
def step_given_corrupted_file(workdir: Path, name: str, directory: str):
    path = workdir / directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\nthe body of this file is not a PDF at all\n")


# When

@when(parsers.re(rf'documents are loaded from {quoted("directory")}'))
def step_when_documents_are_loaded(state: dict, directory: str):
    state["documents"] = []
    state["error"] = None
    try:
        state["documents"] = load_documents(Path(directory))
    except NoDocumentsFoundError as error:
        state["error"] = error


# Then

@then(
    parsers.re(rf'the document list contains (?P<count>\d+) entr(?:y|ies)(?: {quoted("path")})?')
)
def step_then_document_list_entry(state: dict, count: str, path: str | None):
    documents = loaded_documents(state)
    assert len(documents) == int(count)
    if path is not None:
        assert str(documents[0].path) == path


@then("every document has non-empty text content")
def step_then_every_document_has_text(state: dict):
    documents = loaded_documents(state)
    assert documents
    assert all(document.text.strip() for document in documents)


@then('every document has a "path" attribute with its source path')
def step_then_every_document_has_path(state: dict):
    documents = loaded_documents(state)
    assert all(document.path for document in documents)


@then("every document has a fingerprint computed from its content (sha256)")
def step_then_every_document_has_fingerprint(state: dict):
    for document in loaded_documents(state):
        expected = hashlib.sha256(document.text.encode("utf-8")).hexdigest()
        assert document.fingerprint == expected


@then(parsers.re(rf'a warning about the skipped file {quoted("name")} is logged'))
def step_then_warning_logged(caplog: pytest.LogCaptureFixture, name: str):
    messages = logged_messages(caplog, logging.WARNING)
    assert any(name in message for message in messages), f"no warning about {name}: {messages}"


@then(parsers.re(rf'an error for {quoted("name")} is logged'))
def step_then_error_logged(caplog: pytest.LogCaptureFixture, name: str):
    messages = logged_messages(caplog, logging.ERROR)
    assert any(name in message for message in messages), f"no error for {name}: {messages}"


@then("a NoDocumentsFoundError is raised")
def step_then_no_documents_found_error(state: dict):
    assert isinstance(state["error"], NoDocumentsFoundError), (
        f"expected NoDocumentsFoundError, got {state['error']!r}"
    )
