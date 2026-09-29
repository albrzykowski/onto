"""Unit tests for the provider adapters.

Adapters have no Gherkin contract — they only translate `onto.llm.CompletionRequest`
into a provider's own vocabulary and back — so they are tested directly, against a fake
client that records the request instead of calling a real API.
"""

from types import SimpleNamespace

import httpx
import httpx2
import openai
import pytest
from mistralai.models import SDKError

from onto.llm import LLM, CompletionRequest, LLMError
from onto.llm_mistral import MistralLLM
from onto.llm_openai import OpenAILLM

REQUEST = CompletionRequest(model="test-model", prompt="name the concepts", max_tokens=512)
REPLY = '{"classes": [], "relations": []}'

SENT = {
    "model": "test-model",
    "messages": [{"role": "user", "content": "name the concepts"}],
    "max_tokens": 512,
}


class FakeChat:
    """The `chat` resource both SDKs expose; the reply shape they both unwrap."""

    def __init__(self, error: Exception | None = None, content: str | None = REPLY) -> None:
        self.requests: list[dict] = []
        self._error = error
        self._content = content
        self.complete = self._create  # Mistral: client.chat.complete
        self.completions = SimpleNamespace(create=self._create)  # OpenAI: ...completions.create

    def _create(self, **request: object) -> SimpleNamespace:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, error: Exception | None = None, content: str | None = REPLY) -> None:
        self.chat = FakeChat(error, content)
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def __exit__(self, *exception: object) -> None:
        self.closed = True


def openai_error(message: str) -> Exception:
    return openai.APIError(message, httpx2.Request("POST", "https://api.openai.com"), body=None)


def mistral_error(message: str) -> Exception:
    request = httpx.Request("POST", "https://api.mistral.ai")
    return SDKError(message, httpx.Response(429, request=request))


ADAPTERS = [pytest.param(OpenAILLM, id="openai"), pytest.param(MistralLLM, id="mistral")]

PROVIDER_ERRORS = {OpenAILLM: openai_error, MistralLLM: mistral_error}


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_the_request_reaches_the_provider(adapter):
    client = FakeClient()
    llm: LLM = adapter(client=client)

    assert llm.complete(REQUEST) == REPLY
    assert client.chat.requests == [SENT]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_a_provider_failure_becomes_an_llm_error(adapter):
    client = FakeClient(error=PROVIDER_ERRORS[adapter]("rate limited"))
    llm: LLM = adapter(client=client)

    with pytest.raises(LLMError, match="rate limited"):
        llm.complete(REQUEST)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_a_reply_without_content_is_an_empty_string(adapter):
    client = FakeClient(content=None)
    llm: LLM = adapter(client=client)

    assert llm.complete(REQUEST) == ""


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_leaving_the_adapter_closes_the_client(adapter):
    client = FakeClient()

    with adapter(client=client):
        pass

    assert client.closed
