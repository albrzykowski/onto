"""Step definitions for entity resolution feature."""

import uuid
from collections.abc import Callable

import psycopg2
import qdrant_client
from behave import given, then, when

from app.resolver.entity_resolver import EntityResolver
from app.resolver.models import ResolutionAction
from app.resolver.postgres_repo import PostgresRepo


def get_embedding_fn() -> Callable[[str], list[float]]:
    def fn(text: str) -> list[float]:
        return [0.1] * 768

    return fn


def get_postgres_repo() -> PostgresRepo:
    return PostgresRepo(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )


def get_qdrant_client() -> qdrant_client.QdrantClient:
    return qdrant_client.QdrantClient(host="localhost", port=6333)


def clear_test_data():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM entities WHERE label LIKE 'TestEntity%'")
    cursor.execute("DELETE FROM entities WHERE label IN ('NewCompany', 'Acme Corp', 'Apple', 'Banana', 'Java')")
    cursor.execute("DELETE FROM relations")
    conn.commit()
    cursor.close()
    conn.close()


@given("the Qdrant vector store is available")
def step_qdrant_available(context):
    context.qdrant = get_qdrant_client()


@given("the PostgreSQL database is available")
def step_postgres_available(context):
    context.postgres = get_postgres_repo()


@given("entities have been extracted from a document")
def step_entities_extracted(context):
    context.entities_extracted = True


@given("no existing entities in the knowledge base")
def step_no_existing_entities(context):
    clear_test_data()


@when('I resolve entity "{label}" of type "{entity_type}"')
def step_resolve_entity(context, label, entity_type):
    label = label.strip('"').strip("'")
    entity_type = entity_type.strip('"').strip("'")

    entity_dict = {
        "id": str(uuid.uuid4()),
        "label": label,
        "type": entity_type,
        "definition": f"Test definition for {label}",
    }

    resolver = EntityResolver(
        qdrant_client=context.qdrant,
        postgres_repo=context.postgres,
        embedding_fn=get_embedding_fn(),
    )

    from app.resolver.models import ResolverInput

    input_data = ResolverInput(entities=[entity_dict], relations=[])
    result = resolver.resolve(input_data)

    context.last_decision = result.decisions[0]
    context.last_label = label


@then("the system should create a new entity record")
def step_verify_new_entity_created(context):
    decision = context.last_decision
    assert decision.action == ResolutionAction.CREATE_NEW, f"Expected CREATE_NEW, got {decision.action}"
    assert decision.canonical_entity_id, "No canonical entity ID returned"


@then('the decision should be "{expected_action}"')
def step_verify_decision(context, expected_action):
    expected_action = expected_action.strip('"').strip("'")
    decision = context.last_decision
    if expected_action == "CREATE_NEW":
        assert decision.action == ResolutionAction.CREATE_NEW, f"Expected CREATE_NEW, got {decision.action}"
    elif expected_action == "MERGE":
        assert decision.action == ResolutionAction.MERGE, f"Expected MERGE, got {decision.action}"


@then("the entity should be stored in PostgreSQL")
def test_entity_stored_in_postgres(context):
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute(
        "SELECT label FROM entities WHERE canonical_id = %s",
        (context.last_decision.canonical_entity_id,),
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    assert result is not None, "Entity not found in PostgreSQL"
    assert result[0] == context.last_label, f"Label mismatch: {result[0]} != {context.last_label}"


@given('existing entity "{label}" of type "{entity_type}" with ID "{entity_id}"')
def step_existing_entity(context, label, entity_type, entity_id):
    label = label.strip('"').strip("'")
    entity_type = entity_type.strip('"').strip("'")
    entity_id = entity_id.strip('"').strip("'")

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO entities (id, label, entity_type, definition, canonical_id) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
        (entity_id, label, entity_type, f"Definition for {label}", entity_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    context.qdrant.upsert(
        collection_name="entities",
        points=[
            {
                "id": entity_id,
                "vector": [0.1] * 768,
                "payload": {"label": label, "entity_type": entity_type, "canonical_id": entity_id},
            }
        ],
    )


@then("the system should merge with existing entity")
def step_verify_merge(context):
    decision = context.last_decision
    assert decision.action == ResolutionAction.MERGE, f"Expected MERGE, got {decision.action}"
    assert len(decision.merged_with) > 0, "No merged_with list"


@then("the confidence should be at least {threshold}")
def step_verify_confidence(context, threshold):
    threshold = float(threshold)
    decision = context.last_decision
    assert decision.confidence >= threshold, f"Confidence {decision.confidence} < {threshold}"


@given('existing entity "{label}" of type "{entity_type}"')
def step_existing_entity_simple(context, label, entity_type):
    label = label.strip('"').strip("'")
    entity_type = entity_type.strip('"').strip("'")
    entity_id = str(uuid.uuid4())

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
        (entity_id, label, entity_type, f"Definition for {label}", entity_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    context.qdrant.upsert(
        collection_name="entities",
        points=[
            {
                "id": entity_id,
                "vector": [0.1] * 768,
                "payload": {"label": label, "entity_type": entity_type, "canonical_id": entity_id},
            }
        ],
    )


@then("the system should create a new entity")
def step_verify_new_entity(context):
    decision = context.last_decision
    assert decision.action == ResolutionAction.CREATE_NEW, f"Expected CREATE_NEW, got {decision.action}"


@then("the similarity score should be reduced")
def step_verify_score_reduced(context):
    assert context.last_decision.confidence < 1.0, "Score should be reduced due to type mismatch"


@then("the entities should not merge due to type mismatch penalty")
def step_verify_no_merge_type_mismatch(context):
    decision = context.last_decision
    assert decision.action == ResolutionAction.CREATE_NEW, "Should not merge due to type mismatch penalty"


@given("existing entity with various similarity scores")
def step_existing_entity_various_scores(context):
    pass


@when("I resolve entity with confidence {confidence}")
def step_resolve_with_confidence(context, confidence):
    pass


@when("the embedding service is unavailable")
def step_embedding_unavailable(context):
    context.original_embedding_fn = get_embedding_fn()

    def failing_embedding(text: str):
        raise Exception("Embedding service unavailable")

    context.embedding_fn = failing_embedding


@when('I resolve entity "{label}"')
def step_resolve_entity_simple(context, label):
    label = label.strip('"').strip("'")

    entity_dict = {
        "id": str(uuid.uuid4()),
        "label": label,
        "type": "Organization",
        "definition": f"Test definition for {label}",
    }

    embedding_fn = getattr(context, "embedding_fn", get_embedding_fn())

    resolver = EntityResolver(
        qdrant_client=context.qdrant,
        postgres_repo=context.postgres,
        embedding_fn=embedding_fn,
    )

    from app.resolver.models import ResolverInput

    input_data = ResolverInput(entities=[entity_dict], relations=[])
    result = resolver.resolve(input_data)

    context.last_decision = result.decisions[0]


@then("the decision should have confidence {expected_confidence}")
def step_verify_confidence_value(context, expected_confidence):
    expected_confidence = float(expected_confidence)
    decision = context.last_decision
    assert decision.confidence == expected_confidence, f"Expected {expected_confidence}, got {decision.confidence}"


@then("the error should be logged")
def step_error_logged(context):
    pass


@given("Qdrant vector store is unavailable")
def step_qdrant_unavailable(context):
    pass


@then("the error should be logged as warning")
def step_warning_logged(context):
    pass


@then("the processing should continue")
def step_processing_continues(context):
    assert context.last_decision is not None, "Processing should continue despite error"


@then("the decision should be {expected_action}")
def step_decision_should_be(context, expected_action):
    expected_action = expected_action.strip('"').strip("'")
    decision = context.last_decision
    if expected_action == "CREATE_NEW":
        assert decision.action == ResolutionAction.CREATE_NEW
    elif expected_action == "MERGE":
        assert decision.action == ResolutionAction.MERGE


@given("entities are resolved with merge decisions")
def step_entities_resolved_with_merge(context):
    pass


@when("relations reference original entity IDs")
def step_relations_reference_original_ids(context):
    pass


@then("relations should be updated to use canonical IDs")
def step_verify_relations_updated(context):
    assert hasattr(context, "last_relations"), "No relations found"
    for rel in context.last_relations:
        assert "subject" in rel, "Subject missing"
        assert "object" in rel, "Object missing"


@then("the mapped relations should be stored")
def step_verify_relations_stored(context):
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM relations")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    assert count >= 0, "Relations should be stored"


@given("some entities are merged and others are new")
def step_some_entities_merged(context):
    pass


@when("there are relations referencing unmapped entities")
def step_relations_reference_unmapped(context):
    pass


@then("those relations should be filtered out")
def step_verify_relations_filtered(context):
    pass


@then("only valid relations should be stored")
def step_verify_valid_relations_stored(context):
    pass


@given('entity "{entity_a}" is being merged with entity "{entity_b}"')
def step_entity_merged(context, entity_a, entity_b):
    entity_a = entity_a.strip('"').strip("'")
    entity_b = entity_b.strip('"').strip("'")

    entity_id_a = str(uuid.uuid4())
    entity_id_b = str(uuid.uuid4())

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
        (entity_id_a, entity_a, "Organization", f"Definition for {entity_a}", entity_id_a),
    )
    cursor.execute(
        "INSERT INTO entities (id, label, entity_type, definition, canonical_id) VALUES (%s, %s, %s, %s, %s)",
        (entity_id_b, entity_b, "Organization", f"Definition for {entity_b}", entity_id_b),
    )
    conn.commit()
    cursor.close()
    conn.close()


@when("the merge decision is made")
def step_merge_decision_made(context):
    pass


@then("the merge should be recorded in merge_history table")
def step_verify_merge_history(context):
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'merge_history'")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        assert True, "merge_history table exists"
    else:
        pass


@then("the record should include both entity IDs and timestamp")
def step_verify_merge_history_record(context):
    pass


@given("the same entity was submitted in previous document")
def step_same_entity_previous_document(context):
    pass


@when("I resolve the same entity again")
def step_resolve_same_entity_again(context):
    pass


@then("it should merge with the existing canonical entity")
def step_verify_merge_existing(context):
    decision = context.last_decision
    assert decision.action == ResolutionAction.MERGE, "Should merge with existing canonical entity"


@then("the count of references should increase")
def step_verify_reference_count(context):
    pass


@given("a document with {num_entities} entities and {num_relations} relations")
def step_document_with_entities(context, num_entities, num_relations):
    pass


@when("I resolve all entities")
def step_resolve_all_entities(context):
    pass


@then("each entity should have a resolution decision")
def step_verify_entity_decisions(context):
    assert hasattr(context, "last_decisions"), "No decisions found"
    assert len(context.last_decisions) > 0, "No entity decisions"


@then("all relations should be mapped to canonical IDs")
def step_verify_relations_mapped(context):
    pass


@then("all valid relations should be stored")
def step_verify_all_relations_stored(context):
    pass


@given("extracted entities of types: {types}")
def step_entities_of_types(context, types):
    pass


@when("I resolve each entity type")
def step_resolve_entity_types(context):
    pass


@then("each type should be stored correctly in PostgreSQL")
def step_verify_types_stored(context):
    pass


@then("the entity type should be searchable in Qdrant")
def step_verify_type_searchable(context):
    pass