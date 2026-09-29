"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.override_mode_steps import *  # noqa: F401,F403


@scenario("override-mode.feature", "The previous ontology is overwritten")
def test_the_previous_ontology_is_overwritten():
    pass


@scenario("override-mode.feature", "state.json is cleared")
def test_state_json_is_cleared():
    pass


@scenario("override-mode.feature", "All documents are processed again")
def test_all_documents_are_processed_again():
    pass
