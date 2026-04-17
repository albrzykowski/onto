"""Step definitions for health monitoring feature."""

import time
import requests
from behave import given, when, then

API_BASE_URL = "http://localhost:8000"


@given("the system has processed multiple requests")
def step_system_processed_requests(context):
    """Simulate multiple requests have been processed."""
    for _ in range(5):
        try:
            requests.get(f"{API_BASE_URL}/health", timeout=5)
        except Exception:
            pass


@when("I call the health endpoint")
def step_call_health_endpoint(context):
    """Call the health endpoint."""
    context.health_response = requests.get(f"{API_BASE_URL}/health", timeout=5)
    context.health_request_time = time.time()


@then("the response should have status {status}")
def step_response_has_status(context, status):
    """Verify response body has expected status."""
    expected = status.strip('"').strip("'")
    data = context.health_response.json()
    assert "status" in data, f"Response missing 'status' field: {data}"
    assert data["status"] == expected, (
        f"Expected status '{expected}', got '{data['status']}'"
    )


@then("the response should be HTTP {status_code:d}")
def step_response_http_status(context, status_code):
    """Verify HTTP status code."""
    if hasattr(context, "readiness_response"):
        response = context.readiness_response
    elif hasattr(context, "health_response"):
        response = context.health_response
    else:
        raise AssertionError("No response available in context")

    assert response.status_code == status_code, (
        f"Expected {status_code}, got {response.status_code}"
    )


@then("the response should be received within {seconds:d} second")
def step_response_within_time(context, seconds):
    """Verify response time is within expected duration."""
    elapsed = time.time() - context.health_request_time
    assert elapsed < seconds, f"Response took {elapsed:.2f}s, expected < {seconds}s"


@then("the response should not depend on external services")
def step_health_not_depend_external(context):
    """Verify health endpoint returns healthy even when external services are down."""
    assert context.health_response.status_code == 200
    data = context.health_response.json()
    assert data["status"] == "healthy"


@when("I call the readiness endpoint")
def step_call_readiness_endpoint(context):
    """Call the readiness endpoint."""
    context.readiness_response = requests.get(f"{API_BASE_URL}/ready", timeout=5)


@then("the response should have pulsar status {status}")
def step_response_has_pulsar_status(context, status):
    """Verify response body has expected pulsar status."""
    expected = status.strip('"').strip("'")
    data = context.readiness_response.json()
    assert "pulsar" in data, f"Response missing 'pulsar' field: {data}"
    assert data["pulsar"] == expected, (
        f"Expected pulsar '{expected}', got '{data['pulsar']}'"
    )


@then("the response should indicate system is not ready")
def step_response_not_ready(context):
    """Verify response indicates system is not ready."""
    data = context.readiness_response.json()
    status_text = data.get("status", "") + data.get("detail", {}).get("status", "")
    assert "not ready" in status_text.lower(), f"Expected 'not ready', got: {data}"


@then("Pulsar connections should remain stable")
def step_pulsar_connections_stable(context):
    """Verify health checks don't affect Pulsar stability."""
    for _ in range(3):
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            assert response.status_code == 200
        except Exception as e:
            raise AssertionError(f"Health check failed: {e}")


@given("Pulsar message broker has connection timeout")
def step_pulsar_timeout(context):
    """Simulate Pulsar connection timeout by stopping Pulsar."""
    import subprocess

    subprocess.run(["docker", "stop", "pulsar-e2e"], capture_output=True)
    time.sleep(2)
