"""Unit tests for the LiteLLM adapter.

The adapter has no Gherkin contract — it only translates `onto.llm.CompletionRequest` into the
one call LiteLLM exposes and back — so it is tested directly, with `litellm.completion` replaced
by a fake that records the request instead of calling a real API.
"""

from types import SimpleNamespace

import litellm
import pytest

from onto.llm import LLM, CompletionRequest, LLMError
from onto.llm_litellm import LiteLLMLLM

REQUEST = CompletionRequest(model="mistral/test-model", prompt="name the concepts", max_tokens=512)
REPLY = '{"classes": [], "relations": []}'

SENT = {
    "model": "mistral/test-model",
    "messages": [{"role": "user", "content": "name the concepts"}],
    "max_tokens": 512,
    "api_key": "test-key",
}


class FakeCompletion:
    """Stands in for `litellm.completion`, which is a module function and not a client."""

    def __init__(self, error: Exception | None = None, content: str | None = REPLY) -> None:
        self.requests: list[dict] = []
        self._error = error
        self._content = content

    def __call__(self, **request: object) -> SimpleNamespace:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def install(monkeypatch: pytest.MonkeyPatch, fake: FakeCompletion) -> None:
    monkeypatch.setattr(litellm, "completion", fake)


def test_the_request_reaches_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeCompletion()
    install(monkeypatch, fake)
    llm: LLM = LiteLLMLLM(api_key="test-key")

    assert llm.complete(REQUEST) == REPLY
    assert fake.requests == [SENT]


def test_the_model_name_reaches_the_provider_unprefixed_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The provider is part of the model name and nowhere else, so the adapter must send that
    name as it stands. Prefixing it again would send the request to a provider named after
    itself, which LiteLLM cannot resolve."""
    fake = FakeCompletion()
    install(monkeypatch, fake)
    llm: LLM = LiteLLMLLM(api_key="test-key")

    llm.complete(REQUEST)

    assert fake.requests[0]["model"] == "mistral/test-model"


def test_a_provider_failure_becomes_an_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = litellm.RateLimitError(
        message="rate limited", llm_provider="mistral", model="mistral/test-model"
    )
    install(monkeypatch, FakeCompletion(error=failure))
    llm: LLM = LiteLLMLLM(api_key="test-key")

    with pytest.raises(LLMError, match="rate limited"):
        llm.complete(REQUEST)


def test_a_wrong_api_key_becomes_an_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """LiteLLM does not raise `litellm.APIError`; every failure of its derives from
    `openai.APIError`, so catching the former would let every one of them escape the build."""
    wrong_key = litellm.AuthenticationError(
        message="invalid api key", llm_provider="mistral", model="mistral/test-model"
    )
    install(monkeypatch, FakeCompletion(error=wrong_key))
    llm: LLM = LiteLLMLLM(api_key="test-key")

    with pytest.raises(LLMError, match="invalid api key"):
        llm.complete(REQUEST)


def test_a_reply_without_content_is_an_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeCompletion(content=None))
    llm: LLM = LiteLLMLLM(api_key="test-key")

    assert llm.complete(REQUEST) == ""
