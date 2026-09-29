"""Acceptance tests binding Gherkin scenarios to pytest fixtures."""

from pytest_bdd import scenario

from features.steps.cli_steps import *  # noqa: F401,F403


@scenario("cli.feature", "The build command in override mode")
def test_the_build_command_in_override_mode():
    pass


@scenario("cli.feature", "The update command")
def test_the_update_command():
    pass


@scenario("cli.feature", "Missing configuration fails with an error")
def test_missing_configuration_fails_with_an_error():
    pass


@scenario("cli.feature", "Command help")
def test_command_help():
    pass
