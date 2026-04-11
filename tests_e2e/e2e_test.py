"""E2E tests."""
import subprocess
import threading
import time

import pytest
import requests as r

BASE = "http://localhost:8000"
STATUS_OK = 200
STATUS_UNPROCESSABLE_ENTITY = 422
PYTHON = ".venv/bin/python"


@pytest.fixture(scope="module")
def consumer_output():
    output = []
    proc = subprocess.Popen(
        [PYTHON, "-m", "app.queue.consumer"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(3)

    def read_output():
        for line in iter(proc.stdout.readline, b""):
            output.append(line.decode())

    thread = threading.Thread(target=read_output, daemon=True)
    thread.start()

    yield output
    proc.kill()
    thread.join(timeout=1)


@pytest.mark.e2e
def test_health():
    # Given
    # When
    response = r.get(f"{BASE}/health")
    # Then
    assert response.json()["status"] == "healthy"


@pytest.mark.e2e
def test_ready():
    # Given
    # When
    response = r.get(f"{BASE}/ready")
    # Then
    assert response.status_code == STATUS_OK


@pytest.mark.e2e
def test_create_document(created_topics):
    # Given
    tenant_id = "test-doc"
    created_topics.add(tenant_id)
    payload = {"tenant_id": tenant_id, "content": "hello world"}
    # When
    response = r.post(f"{BASE}/documents", json=payload)
    # Then
    assert response.json()["status"] == "accepted"


@pytest.mark.e2e
def test_validation_empty():
    # Given
    payload = {"tenant_id": "", "content": "test"}
    # When
    response = r.post(f"{BASE}/documents", json=payload)
    # Then
    assert response.status_code == STATUS_UNPROCESSABLE_ENTITY


@pytest.mark.e2e
def test_validation_special_chars():
    # Given
    payload = {"tenant_id": "a@#!", "content": "test"}
    # When
    response = r.post(f"{BASE}/documents", json=payload)
    # Then
    assert response.status_code == STATUS_UNPROCESSABLE_ENTITY


@pytest.mark.e2e
def test_document_processed_by_consumer(precreated_topic, consumer_output):
    # Given
    payload = {"tenant_id": precreated_topic, "content": "test content"}
    # When
    r.post(f"{BASE}/documents", json=payload)
    time.sleep(8)
    # Then
    output_text = "".join(consumer_output)
    assert f"Processing document for tenant: {precreated_topic}" in output_text


@pytest.mark.e2e
def test_document_processed_by_pipeline(precreated_topic, consumer_output):
    import os
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    # Given
    payload = {"tenant_id": precreated_topic, "content": "pipeline test content"}
    # When
    r.post(f"{BASE}/documents", json=payload)
    time.sleep(4)
    # Then
    output_text = "".join(consumer_output)
    assert f"Processing document for tenant: {precreated_topic}" in output_text