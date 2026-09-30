"""Adapter for the provider-neutral `onto.dedup.Embedder` contract.

Like the chat adapter, this one serves every provider through LiteLLM: the provider travels in
the model name. The embeddings model is not the chat model — Mistral embeds with `mistral-embed`
while it answers prompts with `mistral-large-latest` — so the name names both, and the
configuration carries it as `embedding_model`.
"""

import litellm
import openai

from onto.dedup import EmbeddingError


class LiteLLMEmbedder:
    """Turns concept names into vectors with the provider named by `model`."""

    def __init__(self, api_key: str | None = None, model: str = "mistral/mistral-embed") -> None:
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
