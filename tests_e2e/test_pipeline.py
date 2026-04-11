"""E2E pipeline tests."""
import subprocess
import threading
import time

import pytest
import requests as r

BASE = "http://localhost:8000"
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


@pytest.fixture(autouse=True, scope="module")
def mock_llm():
    import os
    if os.getenv("MOCK_LLM"):
        from app.pipeline import llm_processor

        async def mock_process(self, text):
            return llm_processor.LLMResponse(
                content=f"Mocked LLM response for: {text[:30]}",
                success=True
            )

        llm_processor.LLMProcessor.process = mock_process
    yield


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
    # Given
    import os
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("MOCK_LLM"):
        pytest.skip("OPENAI_API_KEY not set and MOCK_LLM not enabled")
    payload = {"tenant_id": precreated_topic, "content": "pipeline test content"}
    # When
    r.post(f"{BASE}/documents", json=payload)
    time.sleep(4)
    # Then
    output_text = "".join(consumer_output)
    assert f"Processing document for tenant: {precreated_topic}" in output_text