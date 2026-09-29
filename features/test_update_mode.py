"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.update_mode_steps import *  # noqa: F401,F403


@scenario("update-mode.feature", "An unchanged document is skipped")
def test_an_unchanged_document_is_skipped():
    pass


@scenario("update-mode.feature", "A new document extends the schema")
def test_a_new_document_extends_the_schema():
    pass


@scenario("update-mode.feature", "A duplicate class is detected via embeddings and merged")
def test_a_duplicate_class_is_detected_and_merged():
    pass


@scenario("update-mode.feature", "Related but distinct concepts are not merged")
def test_related_but_distinct_concepts_are_not_merged():
    pass


@scenario(
    "update-mode.feature",
    "Candidates below the similarity threshold are added without LLM verification",
)
def test_candidates_below_the_threshold_are_added_unverified():
    pass


@scenario("update-mode.feature", "A slot type conflict is resolved by the LLM")
def test_a_slot_type_conflict_is_resolved_by_the_llm():
    pass
