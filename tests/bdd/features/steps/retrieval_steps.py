"""Step definitions for entity retrieval feature."""

import asyncio
import uuid
from collections.abc import Callable

import psycopg2
from behave import given, then, when

from app.resolver.entity_retrieval import EntityRetrieval
from app.resolver.qdrant_client import QdrantClientWrapper
from tests.mocks.mock_fixtures import mock_get_embedding


def _get_qdrant_client() -> QdrantClientWrapper:
    return QdrantClientWrapper(host="localhost", port=6333)


def _get_embedding_fn() -> Callable[[str], list[float]]:
    return mock_get_embedding


def _clear_entities():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM entities")
    conn.commit()
    cursor.close()
    conn.close()
    _clear_qdrant()


def _clear_qdrant():
    try:
        qdrant = QdrantClientWrapper()
        qdrant.client.delete(collection_name="entities")
        qdrant._ensure_collection()
    except Exception:
        pass


def _clear_test_entities():
    test_labels = [
        "Mad Hatter",
        "March Hare",
        "Cheshire Cat",
        "White Rabbit",
        "Queen of Hearts",
        "King of Hearts",
        "Dormouse",
        "Alice",
    ]
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    for label in test_labels:
        cursor.execute("DELETE FROM entities WHERE label = %s", (label,))
    conn.commit()
    cursor.close()
    conn.close()
    _clear_qdrant()
    cursor.close()
    conn.close()


@given("a retrieval Qdrant vector store is available")
def _retrieval_step_qdrant(context):
    context.qdrant = _get_qdrant_client()


@given("a mock LLM API is available")
def _retrieval_step_mock_mode(context):
    context.mock_mode = True


@given("the default candidate limit is {limit}")
def _retrieval_step_default_limit(context, limit):
    context.default_candidate_limit = int(limit)


@given("the knowledge base contains entities:")
def _retrieval_step_kb_entities(context):
    _clear_test_entities()
    embedding_fn = _get_embedding_fn()
    qdrant = context.qdrant

    for row in context.table:
        entity_name = row["name"]
        entity_type = row["type"]
        description = row.get("description", "")

        entity_id = str(uuid.uuid4())
        canonical_id = entity_id

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            dbname="onto",
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO entities (id, label, entity_type, definition, canonical_id) VALUES (%s, %s, %s, %s, %s)",
            (entity_id, entity_name, entity_type, description, canonical_id),
        )
        conn.commit()
        cursor.close()
        conn.close()

        embedding = embedding_fn(description)
        qdrant.upsert(
            collection_name="entities",
            points=[
                {
                    "id": entity_id,
                    "vector": embedding,
                    "payload": {
                        "label": entity_name,
                        "entity_type": entity_type,
                        "description": description,
                        "canonical_id": canonical_id,
                    },
                }
            ],
        )


@given("the knowledge base is empty")
def _retrieval_step_kb_empty(context):
    _clear_entities()


@when('I search for candidate entities for "{query}"')
def _retrieval_step_search(context, query):
    query = query.strip('"').strip("'")
    embedding_fn = _get_embedding_fn()
    limit = getattr(context, "default_candidate_limit", 5)

    retrieval = EntityRetrieval(
        qdrant_client=context.qdrant,
        embedding_fn=embedding_fn,
        default_limit=limit,
    )

    context.last_retrieval = asyncio.run(retrieval.retrieve(query=query))


@when('I lookup entity candidates using query "{query}" with type filter "{entity_type}"')
def _retrieval_step_search_with_type(context, query, entity_type):
    query = query.strip('"').strip("'")
    entity_type = entity_type.strip('"').strip("'")
    embedding_fn = _get_embedding_fn()
    limit = getattr(context, "default_candidate_limit", 5)

    retrieval = EntityRetrieval(
        qdrant_client=context.qdrant,
        embedding_fn=embedding_fn,
        default_limit=limit,
    )

    context.last_retrieval = asyncio.run(retrieval.retrieve(query=query, entity_type=entity_type))


@then("the system should query the vector store using description embeddings")
def _retrieval_step_verify_queried(context):
    assert context.last_retrieval is not None, "No retrieval performed"


@then("the system should return a list of candidates")
def _retrieval_step_verify_list(context):
    assert context.last_retrieval is not None, "No retrieval result"
    result = context.last_retrieval
    assert hasattr(result, "candidates"), "Result missing candidates attribute"


@then("the list should contain {count} entities")
def _retrieval_step_verify_count(context, count):
    expected_count = int(count)
    result = context.last_retrieval
    assert result.count() == expected_count, f"Expected {expected_count} candidates, got {result.count()}"


@then("the candidates should be ranked by semantic similarity")
def _retrieval_step_verify_ranked(context):
    result = context.last_retrieval
    candidates = result.candidates

    if len(candidates) < 2:
        return

    for i in range(len(candidates) - 1):
        current_score = candidates[i].get("score", 0)
        next_score = candidates[i + 1].get("score", 0)
        assert current_score >= next_score, "Candidates not ranked by descending similarity"


@then("the system should return an empty list")
def _retrieval_step_verify_empty(context):
    result = context.last_retrieval
    assert result.is_empty(), "Expected empty list"


@then('the first candidate should be "{entity_name}"')
def _retrieval_step_verify_first(context, entity_name):
    entity_name = entity_name.strip('"').strip("'")
    result = context.last_retrieval
    first = result.first()

    assert first is not None, "No candidates returned"
    assert first.get("label") == entity_name, f"Expected {entity_name}, got {first.get('label')}"


@then('the system should rank "{name}" of type "{entity_type}" higher than "{other}"')
def _retrieval_step_verify_ranking_type(context, name, entity_type, other):
    name = name.strip('"').strip("'")
    entity_type = entity_type.strip('"').strip("'")
    other = other.strip('"').strip("'")

    result = context.last_retrieval
    candidates = result.candidates

    name_pos = None
    other_pos = None

    for i, c in enumerate(candidates):
        if c.get("label") == name and c.get("entity_type") == entity_type:
            name_pos = i
        if c.get("label") == other:
            other_pos = i

    assert name_pos is not None, f"Entity {name} not found in candidates"
    assert other_pos is not None, f"Entity {other} not found in candidates"
    assert name_pos < other_pos, f"{name} should rank higher than {other}"


@then("the system should return no more than {limit} candidates")
def _retrieval_step_verify_limit(context, limit):
    expected_limit = int(limit)
    result = context.last_retrieval
    assert result.count() <= expected_limit, f"Expected <= {expected_limit} candidates"


@then("the list should have at most {count} entities")
def _retrieval_step_verify_at_most(context, count):
    expected_count = int(count)
    result = context.last_retrieval
    assert result.count() <= expected_count, f"Expected at most {expected_count}, got {result.count()}"


@given("the knowledge base contains more than 5 entities with descriptions")
def _retrieval_step_kb_many(context):
    _clear_entities()
    embedding_fn = _get_embedding_fn()
    qdrant = context.qdrant

    entities = [
        ("Mad Hatter", "Character", "Eccentric tea party host obsessed with time"),
        ("March Hare", "Character", "Companion of the Hatter at the tea party"),
        ("Dormouse", "Character", "Sleepy character at the tea party"),
        ("Cheshire Cat", "Character", "Grinning cat that can disappear"),
        ("White Rabbit", "Character", "Nervous rabbit obsessed with time"),
        ("Queen of Hearts", "Character", "Tyrannical ruler shouting Off with their heads"),
        ("King of Hearts", "Character", "Timid ruler, husband of the Queen"),
        ("Caterpillar", "Character", "Wise mushroom-dwelling character"),
    ]

    for entity_name, entity_type, description in entities:
        entity_id = str(uuid.uuid4())
        canonical_id = entity_id

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            dbname="onto",
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO entities (id, label, entity_type, definition, canonical_id) VALUES (%s, %s, %s, %s, %s)",
            (entity_id, entity_name, entity_type, description, canonical_id),
        )
        conn.commit()
        cursor.close()
        conn.close()

        embedding = embedding_fn(description)
        qdrant.upsert(
            collection_name="entities",
            points=[
                {
                    "id": entity_id,
                    "vector": embedding,
                    "payload": {
                        "label": entity_name,
                        "entity_type": entity_type,
                        "description": description,
                        "canonical_id": canonical_id,
                    },
                }
            ],
        )

    context.default_candidate_limit = 5


@then('the system should rank "{name}" higher than "{other}"')
def _retrieval_step_verify_ranking(context, name, other):
    name = name.strip('"').strip("'")
    other = other.strip('"').strip("'")

    result = context.last_retrieval
    candidates = result.candidates

    name_pos = None
    other_pos = None

    for i, c in enumerate(candidates):
        if c.get("label") == name:
            name_pos = i
        if c.get("label") == other:
            other_pos = i

    assert name_pos is not None, f"Entity {name} not found in candidates"
    assert other_pos is not None, f"Entity {other} not found in candidates"
    assert name_pos < other_pos, f"{name} should rank higher than {other}"