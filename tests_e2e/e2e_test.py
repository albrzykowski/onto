"""E2E tests."""
import pytest
import requests as r

BASE = "http://localhost:8000"

@pytest.mark.e2e
def test_health(): assert r.get(f"{BASE}/health").json()["status"] == "healthy"

@pytest.mark.e2e
def test_ready(): assert r.get(f"{BASE}/ready").status_code == 200

@pytest.mark.e2e
def test_create_job(): assert r.post(f"{BASE}/jobs", json={"tenant_id": "test", "payload": {}}).json()["status"] == "accepted"

@pytest.mark.e2e
def test_validation_empty(): assert r.post(f"{BASE}/jobs", json={"tenant_id": "", "payload": {}}).status_code == 422

@pytest.mark.e2e
def test_validation_special_chars(): assert r.post(f"{BASE}/jobs", json={"tenant_id": "a@#!", "payload": {}}).status_code == 422