"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.llm_extraction_steps import *  # noqa: F401,F403


@scenario("llm-extraction.feature", "Extracting candidates from a chunk")
def test_extracting_candidates_from_a_chunk():
    pass


@scenario("llm-extraction.feature", "English names regardless of source language")
def test_english_names_regardless_of_source_language():
    pass


@scenario(
    "llm-extraction.feature", "The prompt constrains the LLM to allowed classes and relations"
)
def test_the_prompt_constrains_the_llm_to_allowed_classes_and_relations():
    pass


@scenario("llm-extraction.feature", "The prompt scopes the LLM to domains without allow-lists")
def test_the_prompt_scopes_the_llm_to_domains_without_allow_lists():
    pass


@scenario("llm-extraction.feature", "Batching LLM calls")
def test_batching_llm_calls():
    pass


@scenario("llm-extraction.feature", "An LLM error for one chunk does not abort the build")
def test_an_llm_error_for_one_chunk_does_not_abort_the_build():
    pass


@scenario("llm-extraction.feature", "A reply that is not valid JSON is not taken for an answer")
def test_a_reply_that_is_not_valid_json_is_not_taken_for_an_answer():
    pass
