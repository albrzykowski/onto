from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

VALID_MODES = ("override", "update")

# the only splitting strategy implemented, and validated here rather than at the first
# document: a configuration that survives loading and then fails on use is a bad error
FIXED_CHUNKING = "fixed"

DescribedConcepts = dict[str, str]


class ConfigValidationError(Exception):
    """Raised when the configuration is structurally invalid."""


_described = Annotated[str, Field(min_length=1)]


class BuilderConfig(BaseModel):
    """The ontology to build, and the models and parameters to build it with.

    Every field is required. A configuration that names no domain states nothing about
    what the ontology is for, and the model left to guess produces a narrow ontology that
    looks like a successful build. The two allow-lists are the exception: they carry a
    description per entry, so an empty one is a deliberate "no allow-list" rather than a
    missing key.
    """

    domains: DescribedConcepts
    allowed_classes: DescribedConcepts = Field(default_factory=dict)
    allowed_relations: DescribedConcepts = Field(default_factory=dict)
    mode: str
    model: str
    embedding_model: str
    api_key: _described
    embedding_api_key: _described
    chunking_strategy: str
    max_chunk_tokens: int = Field(ge=1)
    overlap_tokens: int = Field(ge=0)
    batch_size: int = Field(ge=1)
    max_concepts_per_batch: int = Field(ge=1)
    similarity_threshold: float = Field(ge=0.0, le=1.0)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in VALID_MODES:
            raise ConfigValidationError(
                f"Invalid mode: {value!r}. Expected one of {list(VALID_MODES)}."
            )
        return value

    @field_validator("chunking_strategy")
    @classmethod
    def validate_chunking_strategy(cls, value: str) -> str:
        if value != FIXED_CHUNKING:
            raise ConfigValidationError(
                f"Invalid chunking_strategy: {value!r}. Expected {FIXED_CHUNKING!r}."
            )
        return value

    @model_validator(mode="after")
    def validate_concepts(self) -> "BuilderConfig":
        if not self.domains:
            raise ConfigValidationError(
                "domains must name at least one domain; each with a description."
            )
        for field, concepts in (
            ("domains", self.domains),
            ("allowed_classes", self.allowed_classes),
            ("allowed_relations", self.allowed_relations),
        ):
            for name, description in concepts.items():
                if not name.strip() or not description.strip():
                    raise ConfigValidationError(
                        f"{field}[{name!r}] must be a non-empty name with a non-empty"
                        " description; the description is what scopes the prompt."
                    )
        if self.overlap_tokens >= self.max_chunk_tokens:
            # a zero-length window never advances, so the split would loop forever
            raise ConfigValidationError(
                f"overlap_tokens must be below max_chunk_tokens, got"
                f" {self.overlap_tokens} and {self.max_chunk_tokens}."
            )
        return self


def load_config(config_path: str | Path | None = None) -> BuilderConfig:
    """Load a BuilderConfig from a YAML file."""
    path = Path(config_path) if config_path else Path("config.yaml")
    with path.open(encoding="utf-8") as handle:
        config_data = yaml.safe_load(handle) or {}
    if not isinstance(config_data, dict):
        raise ConfigValidationError(
            f"The configuration {path} must be a mapping of field names to values,"
            f" got {type(config_data).__name__}."
        )
    missing = sorted(set(BuilderConfig.model_fields) - set(config_data))
    if missing:
        raise ConfigValidationError(
            f"The configuration {path} is missing required field"
            f"{'s' if len(missing) > 1 else ''}: {', '.join(missing)}."
        )
    try:
        return BuilderConfig(**config_data)
    except ConfigValidationError:
        raise
    except PydanticValidationError as error:
        # a constraint on a single value, e.g. batch_size below 1: the caller is told
        # which field and why, in the one error type every configuration fault uses
        raise ConfigValidationError(f"Invalid configuration {path}: {error}") from error
