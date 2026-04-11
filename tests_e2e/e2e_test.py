"""E2E tests."""
import pytest
import requests as r

BASE = "http://localhost:8000"
STATUS_OK = 200
STATUS_UNPROCESSABLE_ENTITY = 422


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
def test_create_document():
    # Given
    payload = {"tenant_id": "test", "content": "hello world"}
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