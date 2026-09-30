"""Unit tests for the LiteLLM embedding adapter.

Like the chat adapter, this one only translates the `Embedder` contract into the single call
LiteLLM exposes and back, and no Gherkin scenario says so: it is tested directly, with
`litellm.embedding` replaced by a fake that records the request instead of calling a real API.
"""

import litellm
import pytest

from onto.dedup import Embedder, EmbeddingError
from onto.embeddings import LiteLLMEmbedder

TEXTS = ["Vehicle", "Car"]
VECTORS = [[1.0, 0.0], [0.6, 0.8]]


class FakeEmbedding:
    """Stands in for `litellm.embedding`, which is a module function and not a client."""

    def __init__(self, error: Exception | None = None) -> None:
        self.requests: list[dict] = []
        self._error = error

    def __call__(self, **request: object) -> object:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return type("Reply", (), {"data": [{"embedding": vector} for vector in VECTORS]})()


def install(monkeypatch: pytest.MonkeyPatch, fake: FakeEmbedding) -> None:
    monkeypatch.setattr(litellm, "embedding", fake)


def test_the_texts_reach_the_provider_and_come_back_as_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeEmbedding()
    install(monkeypatch, fake)
    embedder: Embedder = LiteLLMEmbedder(api_key="test-key", model="mistral/mistral-embed")

    assert embedder.embed(TEXTS) == VECTORS
    assert fake.requests[0]["input"] == TEXTS
    assert fake.requests[0]["model"] == "mistral/mistral-embed"


def test_the_vectors_keep_the_order_of_the_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeEmbedding())
    embedder: Embedder = LiteLLMEmbedder(api_key="test-key", model="mistral/mistral-embed")

    first, second = embedder.embed(TEXTS)

    assert (first, second) == (VECTORS[0], VECTORS[1])


def test_a_provider_failure_becomes_an_embedding_error(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = litellm.RateLimitError(
        message="rate limited", llm_provider="mistral", model="mistral/mistral-embed"
    )
    install(monkeypatch, FakeEmbedding(error=failure))
    embedder: Embedder = LiteLLMEmbedder(api_key="test-key", model="mistral/mistral-embed")

    with pytest.raises(EmbeddingError, match="rate limited"):
        embedder.embed(TEXTS)


def test_a_wrong_api_key_becomes_an_embedding_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """LiteLLM does not raise `litellm.APIError`; every failure of its derives from
    `openai.APIError`, so catching the former would let every one of them escape the build."""
    wrong_key = litellm.AuthenticationError(
        message="invalid api key", llm_provider="mistral", model="mistral/mistral-embed"
    )
    install(monkeypatch, FakeEmbedding(error=wrong_key))
    embedder: Embedder = LiteLLMEmbedder(api_key="test-key", model="mistral/mistral-embed")

    with pytest.raises(EmbeddingError, match="invalid api key"):
        embedder.embed(TEXTS)
