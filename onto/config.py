import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class ConfigValidationError(Exception):
    """Raised when the configuration is structurally invalid."""


class MissingAPIKeyError(Exception):
    """Raised when no Anthropic API key is available."""


VALID_MODES = ("override", "update")


class BuilderConfig(BaseModel):
    domains: list[str] = Field(default_factory=list)
    allowed_classes: list[str] = Field(default_factory=list)
    allowed_relations: list[str] = Field(default_factory=list)
    domain_descriptions: dict[str, str] = Field(default_factory=dict)
    mode: str = "override"
    chunking_strategy: str = "fixed"
    max_chunk_tokens: int = 2000
    overlap_tokens: int = 200
    similarity_threshold: float = 0.85
    api_key: str | None = Field(default=None, validate_default=True)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in VALID_MODES:
            raise ConfigValidationError(
                f"Invalid mode: {value!r}. Expected one of {list(VALID_MODES)}."
            )
        return value

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, value: str | None) -> str:
        resolved = value or os.getenv("ANTHROPIC_API_KEY")
        if not resolved:
            raise MissingAPIKeyError(
                "No API key provided: set ANTHROPIC_API_KEY or the api_key field."
            )
        return resolved


def load_config(config_path: str | Path | None = None) -> BuilderConfig:
    """Load a BuilderConfig from a YAML file."""
    path = Path(config_path) if config_path else Path("config.yaml")
    with path.open(encoding="utf-8") as handle:
        config_data = yaml.safe_load(handle) or {}
    return BuilderConfig(**config_data)
