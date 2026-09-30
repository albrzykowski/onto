import re
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


_FENCE = re.compile(r"\s*```(?:json)?\s*\n(.*?)\n\s*```\s*", re.DOTALL)


def read_json(reply: str) -> str:
    """Strip the markdown code fence a model wraps its JSON in, and return what is inside.

    Models asked for JSON frequently answer with a fenced block even when told not to, and
    a reply that is valid JSON plus decoration still fails to parse. Only a *complete* fence
    is removed: a reply that stops halfway has no closing fence, so it passes through
    unchanged and fails loudly rather than being silently mangled.
    """
    fenced = _FENCE.fullmatch(reply)
    return fenced.group(1) if fenced else reply
