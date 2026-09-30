"""LiteLLM adapter for the provider-neutral `onto.llm.LLM` contract.

LiteLLM reaches every provider through one `completion` call, so this single adapter answers
for all of them. The provider travels in the model name, which is how LiteLLM decides where a
request goes: `mistral/mistral-large-latest` goes to Mistral, `openai/gpt-4o` to OpenAI. That
name is the only place a provider is named in this project, so a build cannot end up sending
its prompts and its embeddings to two different accounts.

Importing this module requires `litellm` and `openai`. The latter is not a second provider of
this project: LiteLLM answers with OpenAI-shaped responses, so `openai` arrives with it.
"""

import litellm
import openai

from onto.llm import CompletionRequest, LLMError


class LiteLLMLLM:
    """Answers prompts with the provider named by the model."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def complete(self, request: CompletionRequest) -> str:
        """Return the model's reply, or raise `LLMError` if the request failed."""
        try:
            reply = litellm.completion(
                model=request.model,
                messages=[{"role": "user", "content": request.prompt}],
                max_tokens=request.max_tokens,
                api_key=self._api_key,
            )
        # `litellm.APIError` is not the base of LiteLLM's failures: every one of them derives
        # from `openai.APIError` instead, because LiteLLM answers with OpenAI-shaped responses.
        # Catching `litellm.APIError` here matches nothing, not even a wrong key.
        except openai.OpenAIError as error:
            raise LLMError(str(error)) from error
        return reply.choices[0].message.content or ""
