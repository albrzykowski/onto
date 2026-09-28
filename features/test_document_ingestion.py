"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.document_ingestion_steps import *  # noqa: F401,F403


@scenario("document-ingestion.feature", "Loading all supported formats")
def test_loading_all_supported_formats():
    pass


@scenario("document-ingestion.feature", "Skipping unsupported formats")
def test_skipping_unsupported_formats():
    pass


@scenario("document-ingestion.feature", "Recursive discovery")
def test_recursive_discovery():
    pass


@scenario("document-ingestion.feature", "A corrupted document does not abort ingestion")
def test_a_corrupted_document_does_not_abort_ingestion():
    pass


@scenario("document-ingestion.feature", "Document fingerprint")
def test_document_fingerprint():
    pass


@scenario("document-ingestion.feature", "Empty input folder")
def test_empty_input_folder():
    pass
