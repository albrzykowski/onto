"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.abox_generation_steps import *  # noqa: F401,F403


@scenario("abox-generation.feature", "A valid instances file")
def test_a_valid_instances_file():
    pass


@scenario("abox-generation.feature", "Instances validated against the schema")
def test_instances_validated_against_the_schema():
    pass


@scenario("abox-generation.feature", "An instance outside the schema is rejected")
def test_an_instance_outside_the_schema_is_rejected():
    pass


@scenario("abox-generation.feature", "Every instance carries provenance")
def test_every_instance_carries_provenance():
    pass
