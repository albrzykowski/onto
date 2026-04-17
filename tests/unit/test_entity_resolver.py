"""Unit tests for entity_resolver."""
from unittest.mock import AsyncMock

import pytest

from app.resolver.entity_resolver import EntityResolver
from app.resolver.models import (
    ResolutionAction,
    ResolutionDecision,
    ResolverInput,
    ResolverOutput,
)


class MockQdrantClient:
    def __init__(self):
        self.search_similar = AsyncMock(return_value=[])
        self.insert_entity = AsyncMock()
        self.update_canonical_id = AsyncMock()


class MockPostgresRepo:
    def __init__(self):
        self.insert_entity = AsyncMock(return_value="entity-id-123")
        self.update_canonical_id = AsyncMock()
        self.record_merge = AsyncMock()
        self.get_canonical_entity_by_id = AsyncMock(return_value=None)
        self.insert_relation = AsyncMock(return_value="rel-id-123")


def mock_embedding(text: str) -> list[float]:
    return [0.1] * 1536


@pytest.fixture
def mock_qdrant():
    return MockQdrantClient()


@pytest.fixture
def mock_postgres():
    return MockPostgresRepo()


@pytest.fixture
def resolver(mock_qdrant, mock_postgres):
    return EntityResolver(
        qdrant_client=mock_qdrant,
        postgres_repo=mock_postgres,
        embedding_fn=mock_embedding,
        confidence_threshold=0.85,
        top_k=5,
    )


def test_resolver_output_model():
    # Given
    output = ResolverOutput(
        decisions=[
            ResolutionDecision(
                action=ResolutionAction.CREATE_NEW,
                canonical_entity_id="abc-123",
                confidence=1.0,
                merged_with=[],
            )
        ],
        relations=[{"subject": "s1", "predicate": "p1", "object": "o1"}],
    )

    # When
    # Then
    assert len(output.decisions) == 1
    assert output.decisions[0].action == ResolutionAction.CREATE_NEW
    assert len(output.relations) == 1


@pytest.mark.asyncio
async def test_resolver_creates_new_entity_when_no_candidates(resolver, mock_qdrant, mock_postgres):
    # Given
    mock_qdrant.search_similar.return_value = []
    input_data = ResolverInput(
        entities=[{"id": "e1", "label": "Poland", "type": "Location"}],
        relations=[{"subject": "e1", "predicate": "located_in", "object": "e2"}],
    )

    # When
    result = await resolver.resolve(input_data)

    # Then
    assert len(result.decisions) == 1
    assert result.decisions[0].action == ResolutionAction.CREATE_NEW
    mock_postgres.insert_entity.assert_called_once()


@pytest.mark.asyncio
async def test_resolver_merges_when_confidence_above_threshold(resolver, mock_qdrant, mock_postgres):
    # Given
    mock_qdrant.search_similar.return_value = [
        {"id": "existing-1", "score": 0.92, "canonical_id": "canon-1", "entity_type": "Location"}
    ]
    input_data = ResolverInput(
        entities=[{"id": "e1", "label": "Poland", "type": "Location"}],
        relations=[],
    )

    # When
    await resolver.resolve(input_data)

    # Then
    mock_qdrant.search_similar.assert_called_once()


@pytest.mark.asyncio
async def test_resolver_creates_new_when_embedding_fails(mock_qdrant, mock_postgres):
    # Given
    def failing_embedding(text: str):
        raise Exception("API error")

    resolver = EntityResolver(
        qdrant_client=mock_qdrant,
        postgres_repo=mock_postgres,
        embedding_fn=failing_embedding,
    )
    input_data = ResolverInput(
        entities=[{"id": "e1", "label": "Test", "type": "Other"}],
        relations=[],
    )

    # When
    result = await resolver.resolve(input_data)

    # Then
    assert result.decisions[0].action == ResolutionAction.CREATE_NEW
    assert result.decisions[0].confidence == 0.0


def test_resolver_maps_relations_correctly(resolver, mock_qdrant, mock_postgres):
    # Given
    relations = [{"subject": "e1", "predicate": "capital", "object": "e2"}]
    id_map = {"e1": "new-e1", "e2": "new-e2"}

    # When
    mapped = resolver._map_relations(relations, id_map)

    # Then
    assert len(mapped) == 1
    assert mapped[0]["subject"] == "new-e1"
    assert mapped[0]["object"] == "new-e2"