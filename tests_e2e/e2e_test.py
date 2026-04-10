"""E2E tests."""
import pytest
import requests as r

BASE = "http://localhost:8000"


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
    assert response.status_code == 200


@pytest.mark.e2e
def test_create_job():
    # Given
    payload = {"tenant_id": "test", "payload": {}}
    # When
    response = r.post(f"{BASE}/jobs", json=payload)
    # Then
    assert response.json()["status"] == "accepted"


@pytest.mark.e2e
def test_validation_empty():
    # Given
    payload = {"tenant_id": "", "payload": {}}
    # When
    response = r.post(f"{BASE}/jobs", json=payload)
    # Then
    assert response.status_code == 422


@pytest.mark.e2e
def test_validation_special_chars():
    # Given
    payload = {"tenant_id": "a@#!", "payload": {}}
    # When
    response = r.post(f"{BASE}/jobs", json=payload)
    # Then
    assert response.status_code == 422