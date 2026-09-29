"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.provenance_logging_steps import *  # noqa: F401,F403


@scenario("provenance-logging.feature", "Class creation is logged with its source excerpt")
def test_class_creation_is_logged_with_its_source_excerpt():
    pass


@scenario("provenance-logging.feature", "Updates and merges are distinguishable events")
def test_updates_and_merges_are_distinguishable_events():
    pass


@scenario("provenance-logging.feature", "Rejections are logged")
def test_rejections_are_logged():
    pass


@scenario("provenance-logging.feature", "Every log line is valid JSON")
def test_every_log_line_is_valid_json():
    pass


@scenario("provenance-logging.feature", "Skipping a document is logged")
def test_skipping_a_document_is_logged():
    pass
