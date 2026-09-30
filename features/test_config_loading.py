"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.config_loading_steps import *  # noqa: F401,F403


@scenario("config-loading.feature", "Loading a full configuration")
def test_loading_a_full_configuration():
    pass


@scenario("config-loading.feature", "An empty domains mapping is rejected")
def test_an_empty_domains_mapping_is_rejected():
    pass


@scenario("config-loading.feature", "Every domain must carry a description")
def test_every_domain_must_carry_a_description():
    pass


@scenario("config-loading.feature", "Empty allow-lists are valid")
def test_empty_allow_lists_are_valid():
    pass


@scenario("config-loading.feature", "A class on an allow-list must carry a description")
def test_a_class_on_an_allow_list_must_carry_a_description():
    pass


@scenario("config-loading.feature", "A relation on an allow-list must carry a description")
def test_a_relation_on_an_allow_list_must_carry_a_description():
    pass


@scenario("config-loading.feature", "An invalid field value is rejected")
def test_an_invalid_field_value_is_rejected():
    pass


@scenario("config-loading.feature", "A missing required field is rejected")
def test_a_missing_required_field_is_rejected():
    pass
