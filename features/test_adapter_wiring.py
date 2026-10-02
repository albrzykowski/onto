"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.adapter_wiring_steps import *  # noqa: F401,F403


@scenario("adapter-wiring.feature", "The two keys reach their own adapters")
def test_the_two_keys_reach_their_own_adapters():
    pass
