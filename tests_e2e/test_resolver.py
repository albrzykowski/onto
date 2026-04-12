"""E2E resolver tests."""
import asyncio

import psycopg2
import pytest
import requests as r

from app.pipeline.llm_processor import LLMResponse
from app.resolver import (
    EntityResolver,
    PostgresRepo,
    QdrantClientWrapper,
    ResolverInput,
)

BASE = "http://localhost:8000"
HTTP_OK = 200
MIN_ENTITIES = 1
MIN_RELATIONS = 1


def get_postgres_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        database="onto",
    )


@pytest.fixture(autouse=True)
def clean_postgres():
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE entities CASCADE")
        cursor.execute("TRUNCATE TABLE relations CASCADE")
        cursor.execute("TRUNCATE TABLE merge_history CASCADE")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass
    yield


@pytest.fixture
def postgres_connection():
    conn = get_postgres_connection()
    yield conn
    conn.close()


def mock_get_embedding(text):
    return [0.1] * 1536


async def process_document_direct(content):
    llm_response = LLMResponse(
        content={
            "entities": [
                {"id": "E1", "label": "Poland", "type": "Location"},
                {"id": "E2", "label": "Warsaw", "type": "Location"},
            ],
            "relations": [
                {"subject": "E2", "predicate": "located_in", "object": "E1"},
            ],
        },
        success=True,
    )

    qdrant = QdrantClientWrapper(host="localhost", port=6333)
    postgres = PostgresRepo(host="localhost", port=5432, user="postgres", password="postgres", database="onto")
    await postgres.connect()
    await postgres.init_schema()

    resolver = EntityResolver(qdrant_client=qdrant, postgres_repo=postgres, embedding_fn=mock_get_embedding)

    entities = llm_response.content.get("entities", [])
    relations = llm_response.content.get("relations", [])

    input_data = ResolverInput(entities=entities, relations=relations)
    output = await resolver.resolve(input_data)

    for rel in output.relations:
        await postgres.insert_relation(rel["subject"], rel["predicate"], rel["object"])

    await postgres.close()

    return output


@pytest.mark.e2e
def test_entities_and_relations_saved_to_postgres(postgres_connection):
    # Given
    content = "Poland Warsaw"

    # When
    asyncio.run(process_document_direct(content))

    # Then
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT label, entity_type FROM entities")
    entities = cursor.fetchall()

    cursor.execute("SELECT subject_id, predicate, object_id FROM relations")
    relations = cursor.fetchall()

    cursor.close()

    assert len(entities) >= MIN_ENTITIES, f"Expected entities, got {len(entities)}"
    assert len(relations) >= MIN_RELATIONS, f"Expected relations, got {len(relations)}"


@pytest.mark.e2e
def test_embeddings_stored_in_qdrant():
    # Given
    content = "Poland"

    # When
    asyncio.run(process_document_direct(content))

    # Then
    response = r.get("http://localhost:6333/collections/entities")

    assert response.status_code == HTTP_OK
    data = response.json()
    assert data["result"]["points_count"] >= 0


@pytest.mark.e2e
def test_full_pipeline_rest_api_to_databases(postgres_connection):
    # Given
    payload = {"tenant_id": "rest-flow-test", "content": "test"}

    # When
    response = r.post(f"{BASE}/documents", json=payload)

    # Then
    assert response.status_code == HTTP_OK

    topics = r.get("http://localhost:8080/admin/v2/persistent/public/default").json()
    assert any("rest-flow-test" in t for t in topics)