"""Step definitions for document submission feature."""

import requests
from behave import given, when, then

API_BASE_URL = "http://localhost:8000"


@given("the API server is running")
def step_api_server_running(context):
    """Verify API server is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        assert response.status_code == 200, f"API not healthy: {response.status_code}"
        context.api_base_url = API_BASE_URL
    except requests.exceptions.ConnectionError:
        raise AssertionError("API server is not running")


@given("Pulsar message broker is available")
def step_pulsar_available(context):
    """Verify Pulsar is available via Docker container inspection."""
    import subprocess
    import time

    max_retries = 15
    for attempt in range(max_retries):
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Health.Status}}", "pulsar-e2e"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip()
        if "healthy" in output.lower():
            return
        if attempt < max_retries - 1:
            time.sleep(2)

    result = subprocess.run(
        ["docker", "inspect", "--format={{.State.Running}}", "pulsar-e2e"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert "true" in result.stdout.lower(), (
        f"Pulsar container not running: {result.stdout}"
    )


@given("Pulsar message broker is unavailable")
def step_pulsar_unavailable(context):
    """Simulate Pulsar being unavailable by stopping the service."""
    import subprocess

    subprocess.run(["docker", "stop", "pulsar-e2e"], capture_output=True)
    context.pulsar_stopped = True


@when("I submit a document with tenant_id {tenant_id} and content {content}")
def step_submit_document(context, tenant_id, content):
    """Submit a document to the API."""
    # Remove surrounding quotes if present (behave adds them for string params)
    tenant_id = tenant_id.strip('"').strip("'")
    content = content.strip('"').strip("'")

    context.last_response = requests.post(
        f"{API_BASE_URL}/documents",
        json={"tenant_id": tenant_id, "content": content},
        timeout=10,
    )


@when("I submit a document with tenant_id longer than 128 characters")
def step_submit_long_tenant_id(context):
    """Submit a document with tenant_id exceeding 128 characters."""
    long_tenant_id = "a" * 129
    context.last_response = requests.post(
        f"{API_BASE_URL}/documents",
        json={"tenant_id": long_tenant_id, "content": "Some content"},
        timeout=10,
    )


@then("the API should return status {status_code:d}")
def step_api_return_status(context, status_code):
    """Verify API returns expected status code."""
    assert context.last_response.status_code == status_code, (
        f"Expected {status_code}, got {context.last_response.status_code}"
    )


@then("the response should contain status {status}")
def step_response_contains_status(context, status):
    """Verify response body contains expected status field."""
    data = context.last_response.json()
    assert "status" in data, f"Response missing 'status' field: {data}"
    expected = status.strip('"').strip("'")
    assert data["status"] == expected, (
        f"Expected status '{expected}', got '{data['status']}'"
    )


@then("the response should include a job_id")
def step_response_has_job_id(context):
    """Verify response includes a job_id."""
    data = context.last_response.json()
    assert "job_id" in data, f"Response missing 'job_id': {data}"
    assert data["job_id"], "job_id should not be empty"


@then('the response should include the tenant_id "{tenant_id}"')
def step_response_has_tenant_id(context, tenant_id):
    """Verify response includes expected tenant_id."""
    data = context.last_response.json()
    assert "tenant_id" in data, f"Response missing 'tenant_id': {data}"
    assert data["tenant_id"] == tenant_id, (
        f"Expected tenant_id '{tenant_id}', got '{data['tenant_id']}'"
    )


@then("the response should indicate validation error")
def step_response_validation_error(context):
    """Verify response indicates validation error."""
    data = context.last_response.json()
    assert context.last_response.status_code == 422, (
        f"Expected 422, got {context.last_response.status_code}"
    )
    assert "detail" in data or "error" in data, (
        f"Expected validation detail, got: {data}"
    )


@then("the response should include an error message")
def step_response_has_error_message(context):
    """Verify response includes error message."""
    if hasattr(context, "readiness_response"):
        response = context.readiness_response
    elif hasattr(context, "last_response"):
        response = context.last_response
    else:
        raise AssertionError("No response available in context")

    data = response.json()
    assert "error" in data or "detail" in data, (
        f"Response missing error message: {data}"
    )
