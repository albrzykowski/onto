"""OpenAI adapter for the provider-neutral `onto.llm.LLM` contract.

Importing this module requires the `openai` package, which `onto` does not depend on:
install it only if you build with OpenAI.
"""

from types import TracebackType

import openai
from openai.types.chat import ChatCompletionUserMessageParam

from onto.llm import CompletionRequest, LLMError


class OpenAILLM:
    """Answers prompts with the OpenAI chat completions API."""

    def __init__(self, api_key: str | None = None, client: openai.OpenAI | None = None) -> None:
        self._client = client if client is not None else openai.OpenAI(api_key=api_key)

    def complete(self, request: CompletionRequest) -> str:
        """Return the model's reply, or raise `LLMError` if the request failed."""
        message = ChatCompletionUserMessageParam(role="user", content=request.prompt)
        try:
            reply = self._client.chat.completions.create(
                model=request.model,
                messages=[message],
                max_tokens=request.max_tokens,
            )
        except openai.OpenAIError as error:
            raise LLMError(str(error)) from error
        return reply.choices[0].message.content or ""

    def __enter__(self) -> "OpenAILLM":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._client.close()
