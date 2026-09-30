"""Unit tests for the embedding adapters.

Like the chat adapters, these only translate the `Embedder` contract into a provider's own
vocabulary and back, and no Gherkin scenario says so: they are tested directly, against a fake
client that records the request instead of calling a real API.
"""

from types import SimpleNamespace

import httpx
import openai
import pytest
from mistralai.models import SDKError

from onto.dedup import Embedder, EmbeddingError
from onto.embeddings import MistralEmbedder, OpenAIEmbedder

TEXTS = ["Vehicle", "Car"]
VECTORS = [[1.0, 0.0], [0.6, 0.8]]


class FakeEmbeddings:
    """The `embeddings` resource both SDKs expose; the reply shape they both unwrap."""

    def __init__(self, error: Exception | None = None) -> None:
        self.requests: list[dict] = []
        self._error = error

    def create(self, **request: object) -> SimpleNamespace:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=vector) for vector in VECTORS]
        )


class FakeClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.embeddings = FakeEmbeddings(error)
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def __exit__(self, *exception: object) -> None:
        self.closed = True


def openai_error(message: str) -> Exception:
    return openai.APIError(message, httpx.Request("POST", "https://api.openai.com"), body=None)


def mistral_error(message: str) -> Exception:
    request = httpx.Request("POST", "https://api.mistral.ai")
    return SDKError(message, httpx.Response(429, request=request))


ADAPTERS = [pytest.param(OpenAIEmbedder, id="openai"), pytest.param(MistralEmbedder, id="mistral")]

PROVIDER_ERRORS = {OpenAIEmbedder: openai_error, MistralEmbedder: mistral_error}

# the two SDKs spell the argument of an embedding request differently, and neither takes the
# other one, so what each is called is part of the adapter rather than of the contract
REQUEST_FIELDS = {
    OpenAIEmbedder: "input",
    MistralEmbedder: "inputs",
}


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_the_texts_reach_the_provider_and_come_back_as_vectors(adapter):
    client = FakeClient()
    embedder: Embedder = adapter(client=client)

    assert embedder.embed(TEXTS) == VECTORS
    assert client.embeddings.requests[0][REQUEST_FIELDS[adapter]] == TEXTS


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_the_vectors_keep_the_order_of_the_texts(adapter):
    client = FakeClient()
    embedder: Embedder = adapter(client=client)

    first, second = embedder.embed(TEXTS)

    assert (first, second) == (VECTORS[0], VECTORS[1])


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_a_provider_failure_becomes_an_embedding_error(adapter):
    client = FakeClient(error=PROVIDER_ERRORS[adapter]("rate limited"))
    embedder: Embedder = adapter(client=client)

    with pytest.raises(EmbeddingError, match="rate limited"):
        embedder.embed(TEXTS)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_leaving_the_adapter_closes_the_client(adapter):
    client = FakeClient()

    with adapter(client=client):
        pass

    assert client.closed
