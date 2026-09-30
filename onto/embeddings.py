"""Adapter for the provider-neutral `onto.dedup.Embedder` contract.

Like the chat adapter, this one serves every provider through LiteLLM: the provider travels in
the model name, and the embeddings model is not the chat model, so both arrive as one name.

The embedding model differs per provider, so `EMBEDDING_MODELS` is where a provider names the
one that serves it.
"""

import litellm
import openai

from onto.dedup import EmbeddingError

EMBEDDING_MODELS = {
    "mistral": "mistral/mistral-embed",
    "openai": "openai/text-embedding-3-small",
}


class LiteLLMEmbedder:
    """Turns concept names into vectors with the provider named by `model`."""

    def __init__(
        self, api_key: str | None = None, model: str = EMBEDDING_MODELS["mistral"]
    ) -> None:
        self._api_key = api_key
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the order the texts were given."""
        try:
            reply = litellm.embedding(model=self._model, input=texts, api_key=self._api_key)
        # `litellm.APIError` is not the base of LiteLLM's failures: every one of them derives
        # from `openai.APIError` instead, because LiteLLM answers with OpenAI-shaped responses.
        # Catching `litellm.APIError` here matches nothing, not even a wrong key.
        except openai.OpenAIError as error:
            raise EmbeddingError(str(error)) from error
        return [list(item["embedding"]) for item in reply.data]
