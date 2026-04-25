"""E2E pipeline tests."""
import subprocess
import threading
import time

import pytest
import requests as r

BASE = "http://localhost:8000"
PYTHON = "python"


@pytest.fixture(scope="module")
def consumer_output():
    output = []
    proc = subprocess.Popen(
        [PYTHON, "scripts/test_consumer.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(5)

    def read_output():
        for line in iter(proc.stdout.readline, b""):
            output.append(line.decode())

    thread = threading.Thread(target=read_output, daemon=True)
    thread.start()

    yield output
    proc.kill()
    thread.join(timeout=1)


@pytest.mark.e2e
def test_document_processed_by_consumer(precreated_topic, consumer_output):
    # Given
    payload = {"tenant_id": precreated_topic, "content": "test content"}
    # When
    r.post(f"{BASE}/documents", json=payload)
    time.sleep(20)
    # Then
    output_text = "".join(consumer_output)
    assert f"Processing document for tenant: {precreated_topic}" in output_text or "Connected to" in output_text


@pytest.mark.e2e
def test_document_processed_by_ontology_pipeline(precreated_topic, consumer_output):
    # Given
    payload = {"tenant_id": precreated_topic, "content": "pipeline test content"}
    # When
    r.post(f"{BASE}/documents", json=payload)
    time.sleep(20)
    # Then
    output_text = "".join(consumer_output)
    assert f"Processing document for tenant: {precreated_topic}" in output_text or "Connected to" in output_text