"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.abox_generation_steps import *  # noqa: F401,F403

# pytest-bdd registers a step definition in the namespace of the module that defines it,
# so the shared update step in support.py reaches this module only through this import.
from features.steps.support import *  # noqa: F401,F403


@scenario("abox-generation.feature", "A slot value that names a written instance is written")
def test_a_slot_value_that_names_a_written_instance_is_written():
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


@scenario("abox-generation.feature", "A written instance is recorded")
def test_a_written_instance_is_recorded():
    pass


@scenario("abox-generation.feature", "An instance the corpus names again is extended, not restated")
def test_an_instance_the_corpus_names_again_is_extended_not_restated():
    pass


@scenario("abox-generation.feature", "Two wordings of one id do not overwrite each other")
def test_two_wordings_of_one_id_do_not_overwrite_each_other():
    pass
