"""Mistral adapter for the provider-neutral `onto.llm.LLM` contract.

Importing this module requires the `mistralai` package, which `onto` does not depend
on: install it only if you build with Mistral. The wheel published as `mistralai>=3`
is broken, hence the `mistralai<2` requirement in the dev dependency group.
"""

from types import TracebackType

import mistralai
from mistralai.models import MessagesTypedDict, SDKError, UserMessageTypedDict

from onto.llm import CompletionRequest, LLMError


class MistralLLM:
    """Answers prompts with the Mistral chat API."""

    def __init__(self, api_key: str | None = None, client: mistralai.Mistral | None = None) -> None:
        self._client = client if client is not None else mistralai.Mistral(api_key=api_key)

    def complete(self, request: CompletionRequest) -> str:
        """Return the model's reply, or raise `LLMError` if the request failed."""
        messages: list[MessagesTypedDict] = [
            UserMessageTypedDict(role="user", content=request.prompt)
        ]
        try:
            reply = self._client.chat.complete(
                model=request.model,
                messages=messages,
                max_tokens=request.max_tokens,
            )
        except SDKError as error:
            raise LLMError(str(error)) from error
        content = reply.choices[0].message.content
        return content if isinstance(content, str) else ""

    def __enter__(self) -> "MistralLLM":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._client.__exit__(exception_type, exception, traceback)
