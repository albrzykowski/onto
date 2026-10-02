"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.tbox_generation_steps import *  # noqa: F401,F403


@scenario("tbox-generation.feature", "A valid LinkML schema")
def test_a_valid_linkml_schema():
    pass


@scenario("tbox-generation.feature", "Schema validation")
def test_schema_validation():
    pass


@scenario("tbox-generation.feature", "Classes carry descriptions and provenance")
def test_classes_carry_descriptions_and_provenance():
    pass


@scenario("tbox-generation.feature", "Schema consolidation over a large corpus")
def test_schema_consolidation_over_a_large_corpus():
    pass


@scenario("tbox-generation.feature", "A class is assigned only the slots the schema has")
def test_a_class_is_assigned_only_the_slots_the_schema_has():
    pass


@scenario("tbox-generation.feature", "Slot creation is logged with its source excerpt")
def test_slot_creation_is_logged_with_its_source_excerpt():
    pass
