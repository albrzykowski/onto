from pathlib import Path
from typing import Any

import yaml
from pytest_bdd import given, parsers, then, when

from features.steps.support import VALID_CONFIG, quoted
from onto.config import ConfigValidationError, load_config


def write_config(config_path: Path, data: dict[str, Any]) -> None:
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")


# Given: configuration files

@given('a configuration file "config.yaml" containing:')
def step_given_config_file_full(config_path: Path, datatable: list) -> None:
    """The data table is the whole configuration; every value is YAML, so a map is written
    the way it would be in the file itself."""
    rows = [row.cells() if hasattr(row, "cells") else row for row in datatable]
    write_config(config_path, {key: yaml.safe_load(value) for key, value in rows})


@given('a configuration file with an empty "domains" mapping')
def step_given_config_empty_domains(config_path: Path) -> None:
    write_config(config_path, {**VALID_CONFIG, "domains": {}})


@given(
    parsers.re(
        rf'a configuration file with the domain {quoted("domain")} having an empty description'
    )
)
def step_given_config_domain_without_description(
    config_path: Path, domain: str
) -> None:
    write_config(config_path, {**VALID_CONFIG, "domains": {domain: ""}})


@given("a configuration file with all required fields")
def step_given_config_with_all_fields(config_path: Path) -> None:
    write_config(config_path, dict(VALID_CONFIG))


@given('allowed_classes set to an empty mapping')
def step_given_allowed_classes_empty_mapping(config_path: Path) -> None:
    write_config(config_path, {**VALID_CONFIG, "allowed_classes": {}})


@given('allowed_relations set to an empty mapping')
def step_given_allowed_relations_empty_mapping(config_path: Path) -> None:
    write_config(config_path, {**VALID_CONFIG, "allowed_relations": {}})


@given(
    parsers.re(
        rf'a configuration file with allowed_classes containing the class {quoted("name")} '
        rf'without a description'
    )
)
def step_given_allowed_class_without_description(config_path: Path, name: str) -> None:
    write_config(config_path, {**VALID_CONFIG, "allowed_classes": {name: ""}})


@given(
    parsers.re(
        rf'a configuration file with allowed_relations containing the relation {quoted("name")} '
        rf'without a description'
    )
)
def step_given_allowed_relation_without_description(config_path: Path, name: str) -> None:
    write_config(config_path, {**VALID_CONFIG, "allowed_relations": {name: ""}})


@given(
    parsers.re(rf'a configuration file with the field {quoted("field")} set to {quoted("value")}')
)
def step_given_config_field_with_value(config_path: Path, field: str, value: str) -> None:
    write_config(config_path, {**VALID_CONFIG, field: yaml.safe_load(value)})


@given(
    parsers.re(rf'a configuration file with every required field except {quoted("field")}')
)
def step_given_config_without_field(config_path: Path, field: str) -> None:
    data = dict(VALID_CONFIG)
    del data[field]
    write_config(config_path, data)


# When

@when("the configuration is loaded")
def step_when_config_loaded(config_path: Path, state: dict) -> None:
    state["config"] = None
    state["error"] = None
    try:
        state["config"] = load_config(config_path)
    except ConfigValidationError as error:
        state["error"] = error


# Then: the full configuration

@then(
    parsers.re(
        rf'the BuilderConfig contains the domain {quoted("domain")} with the description '
        rf'{quoted("description")}'
    )
)
def step_then_config_contains_domain(config, domain: str, description: str) -> None:
    assert config.domains.get(domain) == description, f"domains are {config.domains}"


@then(
    parsers.re(
        rf'the allowed classes contain {quoted("first")} with its description and '
        rf'{quoted("second")} with its description'
    )
)
def step_then_allowed_classes_with_descriptions(config, first: str, second: str) -> None:
    for name in (first, second):
        assert name in config.allowed_classes, f"allowed classes are {config.allowed_classes}"
        assert config.allowed_classes[name], f"{name} has no description"


@then(parsers.re(rf'the allowed relations contain {quoted("name")} with its description'))
def step_then_allowed_relation_with_description(config, name: str) -> None:
    assert name in config.allowed_relations, f"allowed relations are {config.allowed_relations}"
    assert config.allowed_relations[name], f"{name} has no description"


@then('the operating mode is "update"')
def step_then_mode_is_update(config) -> None:
    assert config.mode == "update"


@then(parsers.re(rf'the model is {quoted("name")}'))
def step_then_model(config, name: str) -> None:
    assert config.model == name


@then(parsers.re(rf'the embedding model is {quoted("name")}'))
def step_then_embedding_model(config, name: str) -> None:
    assert config.embedding_model == name


@then('the chunking strategy is "fixed"')
def step_then_chunking_strategy(config) -> None:
    assert config.chunking_strategy == "fixed"


@then("max_chunk_tokens is 2000, overlap_tokens is 200, batch_size is 4")
def step_then_chunking_bounds(config) -> None:
    assert config.max_chunk_tokens == 2000
    assert config.overlap_tokens == 200
    assert config.batch_size == 4


@then("max_concepts_per_batch is 5 and similarity_threshold is 0.85")
def step_then_extraction_bounds(config) -> None:
    assert config.max_concepts_per_batch == 5
    assert config.similarity_threshold == 0.85


# Then: empty allow-lists

@then("the allowed classes list is empty")
def step_then_allowed_classes_empty(config) -> None:
    assert config.allowed_classes == {}


@then("the allowed relations list is empty")
def step_then_allowed_relations_empty(config) -> None:
    assert config.allowed_relations == {}


# Then: rejection

@then("a ConfigValidationError is raised")
def step_then_config_validation_error(state: dict) -> None:
    assert isinstance(state["error"], ConfigValidationError), (
        f"expected ConfigValidationError, got {state['error']!r}"
    )


@then(parsers.re(rf'a ConfigValidationError is raised with a message naming {quoted("field")}'))
def step_then_config_validation_error_naming(state: dict, field: str) -> None:
    assert isinstance(state["error"], ConfigValidationError), (
        f"expected ConfigValidationError, got {state['error']!r}"
    )
    assert field in str(state["error"]), f"{field!r} not named in {state['error']}"
