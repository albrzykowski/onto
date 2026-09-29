"""Adapters for the provider-neutral `onto.dedup.Embedder` contract.

Like the chat adapters, importing this module requires the SDKs of the providers, which `onto`
does not depend on: install the one you configure.
"""

from types import TracebackType

import mistralai
import openai
from mistralai.models import SDKError

from onto.dedup import EmbeddingError

MISTRAL_EMBEDDING_MODEL = "mistral-embed"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


class MistralEmbedder:
    """Turns concept names into vectors with the Mistral embeddings API."""

    def __init__(
        self,
        api_key: str | None = None,
        client: mistralai.Mistral | None = None,
        model: str = MISTRAL_EMBEDDING_MODEL,
    ) -> None:
        self._client = client if client is not None else mistralai.Mistral(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the order the texts were given."""
        try:
            reply = self._client.embeddings.create(model=self._model, inputs=texts)
        except SDKError as error:
            raise EmbeddingError(str(error)) from error
        return [list(item.embedding or []) for item in reply.data]

    def __enter__(self) -> "MistralEmbedder":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._client.__exit__(exception_type, exception, traceback)


class OpenAIEmbedder:
    """Turns concept names into vectors with the OpenAI embeddings API."""

    def __init__(
        self,
        api_key: str | None = None,
        client: openai.OpenAI | None = None,
        model: str = OPENAI_EMBEDDING_MODEL,
    ) -> None:
        self._client = client if client is not None else openai.OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the order the texts were given."""
        try:
            reply = self._client.embeddings.create(model=self._model, input=texts)
        except openai.OpenAIError as error:
            raise EmbeddingError(str(error)) from error
        return [list(item.embedding) for item in reply.data]

    def __enter__(self) -> "OpenAIEmbedder":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._client.close()
