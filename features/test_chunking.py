"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.chunking_steps import *  # noqa: F401,F403


@scenario("chunking.feature", "A long document is split")
def test_a_long_document_is_split():
    pass


@scenario("chunking.feature", "A short document becomes a single chunk")
def test_a_short_document_becomes_a_single_chunk():
    pass


@scenario("chunking.feature", "Overlap between adjacent chunks")
def test_overlap_between_adjacent_chunks():
    pass


@scenario("chunking.feature", "A chunk keeps a reference to its document")
def test_a_chunk_keeps_a_reference_to_its_document():
    pass
