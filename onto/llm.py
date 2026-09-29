from typing import Protocol

from pydantic import BaseModel, Field


class LLMError(Exception):
    """Raised when a completion request fails — the unit a caller may retry."""


class CompletionRequest(BaseModel):
    """One prompt sent to a model, phrased so any provider can be translated into it."""

    model: str
    prompt: str
    max_tokens: int = Field(ge=1)


class LLM(Protocol):
    """What the build needs from a language model.

    An implementation is the single place a provider appears: it translates the
    request into that provider's own vocabulary, and its failures into `LLMError`.
    """

    def complete(self, request: CompletionRequest) -> str: ...
