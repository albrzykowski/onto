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

# LiteLLM's own default is 6000 seconds, which is over an hour of a build waiting on a
# provider that never answers. Long enough for a batch of dense prose to be answered, short
# enough that such a request does not hold a build open. Both adapters wait the same time, so
# one build cannot be waiting on a chat answer for longer than on its embeddings.
TIMEOUT_SECONDS = 120

# A provider answers a burst of requests with a transient failure more often than it fails
# for good, and the callers treat `LLMError` as the unit worth retrying: extraction logs it
# and skips the batch, which would drop every concept that batch stated. Retrying here turns
# a blip into an answer; a fault that is not transient still raises, once the attempts run out.
NUM_RETRIES = 3


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
                timeout=TIMEOUT_SECONDS,
                max_retries=NUM_RETRIES,
            )
        # `litellm.APIError` is not the base of LiteLLM's failures: every one of them derives
        # from `openai.APIError` instead, because LiteLLM answers with OpenAI-shaped responses.
        # Catching `litellm.APIError` here matches nothing, not even a wrong key.
        except openai.OpenAIError as error:
            raise LLMError(str(error)) from error
        return reply.choices[0].message.content or ""
