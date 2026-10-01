"""Unit tests for the LiteLLM embedding adapter.

Like the chat adapter, this one only translates the `Embedder` contract into the single call
LiteLLM exposes and back, and no Gherkin scenario says so: it is tested directly, with
`litellm.embedding` replaced by a fake that records the request instead of calling a real API.
"""

import inspect

import litellm
import pytest

from onto.dedup import Embedder, EmbeddingError
from onto.embeddings import LiteLLMEmbedder
from onto.llm_litellm import NUM_RETRIES, TIMEOUT_SECONDS

TEXTS = ["Vehicle", "Car"]
VECTORS = [[1.0, 0.0], [0.6, 0.8]]

RETRY_KEYWORDS = ("max_retries", "num_retries")


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


def test_the_call_is_bounded_in_time_and_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider that never answers must not hold a build open, and a transient failure must
    not cost the run the concepts the batch stated."""
    fake = FakeEmbedding()
    install(monkeypatch, fake)
    embedder: Embedder = LiteLLMEmbedder(api_key="test-key", model="mistral/mistral-embed")

    embedder.embed(TEXTS)

    assert fake.requests[0]["timeout"] == TIMEOUT_SECONDS
    assert fake.requests[0]["max_retries"] == NUM_RETRIES


def test_the_retry_keyword_reaches_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    """`litellm.embedding` answers to `max_retries` and not to `num_retries`, and it reads the
    count out of `**kwargs` so neither name is in the signature.

    A fake records whatever it is handed, so sending the name this call ignores still looks
    like sending a retry count: the build would drop every concept a transient failure cost
    it while this file's other tests stayed green. Hence the keyword the adapter sent is
    checked against the real function.
    """
    source = inspect.getsource(litellm.embedding)  # before the fake takes litellm's place
    fake = FakeEmbedding()
    install(monkeypatch, fake)
    embedder: Embedder = LiteLLMEmbedder(api_key="test-key", model="mistral/mistral-embed")

    embedder.embed(TEXTS)

    sent = [name for name in fake.requests[0] if name in RETRY_KEYWORDS]
    assert len(sent) == 1, f"expected one retry keyword, sent {fake.requests[0]}"
    assert f'kwargs.get("{sent[0]}"' in source, f"litellm.embedding never reads {sent[0]}"


def test_the_key_is_sent_to_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """`api_key` on its own is not a credential the provider recognises: LiteLLM will not look
    it up from the environment for a request that names one, so a build that forgets to pass it
    leaves without credentials and is answered `Invalid API Key` — the same as a wrong key."""
    fake = FakeEmbedding()
    install(monkeypatch, fake)
    embedder: Embedder = LiteLLMEmbedder(api_key="test-key", model="mistral/mistral-embed")

    embedder.embed(TEXTS)

    assert fake.requests[0]["api_key"] == "test-key"


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
