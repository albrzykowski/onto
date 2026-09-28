"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from features.steps.config_loading_steps import *  # noqa: F401,F403
from pytest_bdd import scenario

@scenario("config-loading.feature", "Loading a full configuration")
def test_loading_a_full_configuration():
    pass


@scenario("config-loading.feature", "Domains carry descriptions")
def test_domains_carry_descriptions():
    pass


@scenario("config-loading.feature", "Default values for a minimal configuration")
def test_default_values_for_a_minimal_configuration():
    pass


@scenario("config-loading.feature", "Rejecting an invalid configuration")
def test_rejecting_an_invalid_configuration():
    pass


@scenario("config-loading.feature", "API key from environment variable")
def test_api_key_from_environment_variable():
    pass


@scenario("config-loading.feature", "Missing API key")
def test_missing_api_key():
    pass
