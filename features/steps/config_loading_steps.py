from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, when, then

from onto.config import ConfigValidationError, MissingAPIKeyError, load_config


TEST_API_KEY = "sk-ant-test"


def write_config(config_path: Path, data: dict, *, with_api_key: bool = True) -> None:
    if with_api_key:
        data = {**data, "api_key": TEST_API_KEY}
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")


# Given: configuration files

@given('a configuration file "config.yaml" containing:')
def step_given_config_file_full(config_path):
    write_config(
        config_path,
        {
            "domains": ["automotive", "supply_chain"],
            "allowed_classes": ["Vehicle", "Engine"],
            "allowed_relations": ["has_engine"],
            "mode": "update",
        },
    )


@given('a configuration file containing only "mode: override"')
def step_given_config_minimal(config_path):
    write_config(config_path, {"mode": "override"})


@given(
    'a configuration file with a domain "automotive" described as '
    '"Passenger and commercial vehicles and their components"'
)
def step_given_config_with_domain_desc(config_path):
    description = "Passenger and commercial vehicles and their components"
    write_config(
        config_path,
        {"domains": ["automotive"], "domain_descriptions": {"automotive": description}},
    )


@given('a configuration file with "mode: invalid_mode"')
def step_given_config_invalid_mode(config_path):
    write_config(config_path, {"mode": "invalid_mode"})


@given("the configuration does not contain an api_key")
def step_given_config_without_api_key(config_path):
    write_config(config_path, {"mode": "override"}, with_api_key=False)


# Given: environment

@given('the environment variable ANTHROPIC_API_KEY has the value "sk-ant-test"')
def step_given_api_key_env_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", TEST_API_KEY)


@given("the environment variable ANTHROPIC_API_KEY is not set")
def step_given_api_key_env_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# When

@when("the configuration is loaded")
def step_when_config_loaded(config_path, state):
    state["config"] = None
    state["error"] = None
    try:
        state["config"] = load_config(str(config_path))
    except (ConfigValidationError, MissingAPIKeyError) as error:
        state["error"] = error


# Then: full configuration

@then('the BuilderConfig contains domain "automotive"')
def step_then_contains_domain(config):
    assert "automotive" in config.domains


@then('the allowed classes contain "Vehicle" and "Engine"')
def step_then_allowed_classes(config):
    assert "Vehicle" in config.allowed_classes
    assert "Engine" in config.allowed_classes


@then('the allowed relations contain "has_engine"')
def step_then_allowed_relations(config):
    assert "has_engine" in config.allowed_relations


@then('the operating mode is "update"')
def step_then_mode_is_update(config):
    assert config.mode == "update"


# Then: domain descriptions

@then(
    'the domain "automotive" has the description '
    '"Passenger and commercial vehicles and their components"'
)
def step_then_domain_description(config):
    description = "Passenger and commercial vehicles and their components"
    assert "automotive" in config.domains
    assert config.domain_descriptions.get("automotive") == description


# Then: defaults

@then("the domain list is empty")
def step_then_domains_empty(config):
    assert config.domains == []


@then("the allowed classes list is empty")
def step_then_allowed_classes_empty(config):
    assert config.allowed_classes == []


@then("the allowed relations list is empty")
def step_then_allowed_relations_empty(config):
    assert config.allowed_relations == []


@then('the chunking strategy is "fixed"')
def step_then_chunking_strategy(config):
    assert config.chunking_strategy == "fixed"


@then("the similarity threshold is 0.85")
def step_then_similarity_threshold(config):
    assert config.similarity_threshold == 0.85


# Then: API key

@then('the LLM client is initialized with the key "sk-ant-test"')
def step_then_api_key_from_env(config):
    assert config.api_key == TEST_API_KEY


# Then: errors

@then("a ConfigValidationError is raised")
def step_then_config_validation_error(state):
    assert isinstance(state["error"], ConfigValidationError), (
        f"expected ConfigValidationError, got {state['error']!r}"
    )


@then("a MissingAPIKeyError is raised")
def step_then_missing_api_key_error(state):
    assert isinstance(state["error"], MissingAPIKeyError), (
        f"expected MissingAPIKeyError, got {state['error']!r}"
    )
