"""The keys the configuration names, read off the requests LiteLLM receives.

Both LiteLLM entry points are module functions, so the adapter has no client to substitute and
the wiring is checked where the key is actually consumed: the keyword arguments a fake
`litellm.completion` and `litellm.embedding` record. Asserting on the adapter's own attribute
would only repeat its constructor.
"""

from types import SimpleNamespace

import litellm
import pytest
from pytest_bdd import given, parsers, then, when

from features.steps.support import quoted, valid_config
from onto.cli import embedder_for, llm_for
from onto.llm import CompletionRequest

REQUEST = CompletionRequest(model="openai/gpt-4o", prompt="name the concepts", max_tokens=512)
TEXTS = ["Vehicle"]


def config(state: dict) -> dict:
    return state["config"]


# Given: what the configuration states


@given(
    parsers.re(
        rf"the configuration has model {quoted('model')} and api_key {quoted('api_key')}"
    )
)
def step_given_configuration_has_model_and_api_key(
    state: dict, model: str, api_key: str
) -> None:
    state["config"] = {"model": model, "api_key": api_key}


@given(
    parsers.re(
        rf"the configuration has embedding_model {quoted('model')} and embedding_api_key "
        rf"{quoted('api_key')}"
    )
)
def step_given_configuration_has_embedding_model_and_api_key(
    state: dict, model: str, api_key: str
) -> None:
    state["config"].update(embedding_model=model, embedding_api_key=api_key)


# When: the run builds its adapters


@when("the adapters are built for the run")
def step_when_the_adapters_are_built(state: dict) -> None:
    state["llm"] = llm_for(valid_config(**state["config"]))
    state["embedder"] = embedder_for(valid_config(**state["config"]))


# Then: the keys each adapter sends

_FAKE_REPLY = '{"instances": []}'
_FAKE_VECTORS = [[1.0, 0.0]]


@then(parsers.re(rf"the LLM adapter is given the key {quoted('key')}"))
def step_then_llm_adapter_is_given_the_key(
    state: dict, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    requests: list[dict] = []

    def completion(**request: object) -> object:
        requests.append(request)
        message = SimpleNamespace(content=_FAKE_REPLY)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(litellm, "completion", completion)

    state["llm"].complete(REQUEST)

    assert requests[0]["api_key"] == key, requests[0]


@then(parsers.re(rf"the embedder adapter is given the key {quoted('key')}"))
def step_then_embedder_adapter_is_given_the_key(
    state: dict, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    requests: list[dict] = []

    def embedding(**request: object) -> object:
        requests.append(request)
        return SimpleNamespace(data=[{"embedding": vector} for vector in _FAKE_VECTORS])

    monkeypatch.setattr(litellm, "embedding", embedding)

    state["embedder"].embed(TEXTS)

    assert requests[0]["api_key"] == key, requests[0]
