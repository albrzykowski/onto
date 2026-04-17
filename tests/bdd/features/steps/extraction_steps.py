"""Step definitions for entity extraction feature."""

import time
import psycopg2
import requests
from behave import given, when, then

API_BASE_URL = "http://localhost:8000"


@given("the LLM API is configured with mock mode")
def step_llm_mock_mode(context):
    """Verify MOCK_LLM environment is set (checked via docker-compose)."""
    context.mock_mode = True


@given("the document processing pipeline is operational")
def step_pipeline_operational(context):
    """Verify API and consumer are running."""
    response = requests.get(f"{API_BASE_URL}/health", timeout=5)
    assert response.status_code == 200, "API not operational"


@when("I submit a document with content {content}")
def step_submit_document_for_extraction(context, content):
    """Submit a document for processing."""
    content = content.strip('"').strip("'")
    context.doc_response = requests.post(
        f"{API_BASE_URL}/documents",
        json={"tenant_id": "test-tenant", "content": content},
        timeout=10,
    )
    context.last_response = context.doc_response


@when("the document is processed by the consumer")
def step_wait_for_processing(context):
    """Wait for consumer to process the document."""
    time.sleep(3)
    context.last_response = context.doc_response


@then("the extracted entities should include {entity}")
def step_verify_entity_extracted(context, entity):
    """Verify entity was extracted and stored in PostgreSQL."""
    entity = entity.strip('"').strip("'")

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute("SELECT label FROM entities WHERE label = %s", (entity,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    assert result is not None, f"Entity '{entity}' not found in database"


@then("relations should be extracted and stored")
def step_verify_relations_exist(context):
    """Verify at least one relation was extracted and stored."""
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

    assert count > 0, "No relations found in database"


@then("relations should include a link from {source} to {target}")
def step_verify_relation_exists(context, source, target):
    """Verify relation was extracted and stored in PostgreSQL."""
    source = source.strip('"').strip("'")
    target = target.strip('"').strip("'")

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM relations r
        JOIN entities s ON r.subject_id::text = s.id::text
        JOIN entities o ON r.object_id::text = o.id::text
        WHERE s.label = %s AND o.label = %s
        """,
        (source, target),
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    assert result is not None, (
        f"Relation from '{source}' to '{target}' not found in database"
    )


@then("the relation type should be {relation_type}")
def step_verify_relation_type(context, relation_type):
    """Verify relation has expected type."""
    relation_type = relation_type.strip('"').strip("'")

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    cursor.execute(
        "SELECT predicate FROM relations WHERE predicate = %s LIMIT 1",
        (relation_type,),
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    assert result is not None, f"Relation type '{relation_type}' not found in database"


@then("the processing should complete without error")
def step_verify_processing_complete(context):
    """Verify document was processed without errors."""
    assert context.doc_response.status_code in (200, 202)


@then("the extracted entities should be:")
def step_verify_extracted_entities(context):
    """Verify extracted entities match expected table."""
    import time
    time.sleep(3)

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    for row in context.table:
        entity = row["entity"]
        entity_type = row["type"]
        definition = row.get("definition", "")
        cursor.execute(
            "SELECT definition FROM entities WHERE label = %s AND entity_type = %s",
            (entity, entity_type),
        )
        result = cursor.fetchone()
        assert result is not None, (
            f"Entity '{entity}' with type '{entity_type}' not found in database"
        )
        if definition:
            assert result[0] is not None, (
                f"Entity '{entity}' definition is NULL in database"
            )
            assert definition.lower() in result[0].lower(), (
                f"Entity '{entity}' definition mismatch. Expected '{definition}', got '{result[0]}'"
            )
    cursor.close()
    conn.close()


@then("the extracted relation should be:")
def step_verify_extracted_relation(context):
    """Verify extracted relation matches expected table."""
    import time
    time.sleep(3)

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="onto",
    )
    cursor = conn.cursor()
    for row in context.table:
        subject = row["subject"]
        predicate = row["predicate"]
        obj = row["object"]
        cursor.execute(
            """
            SELECT 1 FROM relations r
            JOIN entities s ON r.subject_id::text = s.canonical_id::text
            JOIN entities o ON r.object_id::text = o.canonical_id::text
            WHERE s.label = %s AND r.predicate = %s AND o.label = %s
            """,
            (subject, predicate, obj),
        )
        result = cursor.fetchone()
        assert result is not None, (
            f"Relation from '{subject}' --[{predicate}]--> '{obj}' not found in database"
        )
    cursor.close()
    conn.close()
