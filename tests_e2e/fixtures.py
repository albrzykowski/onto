"""Fixtures for E2E tests."""
from app.pipeline.llm_processor import LLMProcessor, LLMResponse


MOCK_ENTITIES = {
    "entities": [
        {"id": "E1", "label": "Poland", "type": "Location"},
        {"id": "E2", "label": "Warsaw", "type": "Location"},
    ],
    "relations": [
        {"subject": "E2", "predicate": "located_in", "object": "E1"},
    ],
}


def mock_get_embedding(text: str) -> list[float]:
    """Mock embedding for testing. Returns fixed vector based on text hash."""
    hash_val = hash(text) % 1000
    base = hash_val / 1000.0
    return [base] * 1536


class MockLLMProcessor(LLMProcessor):
    """Mock LLM processor for E2E tests."""

    async def process(self, text: str) -> LLMResponse:
        if not text:
            return LLMResponse(content={}, success=False, error="Empty text")
        return LLMResponse(content=MOCK_ENTITIES, success=True)