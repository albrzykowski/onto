"""E2E tests."""
import requests as r

BASE = "http://localhost:8000"

def test_health(): assert r.get(f"{BASE}/health").json()["status"] == "healthy"
def test_ready(): assert r.get(f"{BASE}/ready").status_code == 200
def test_create_job(): assert r.post(f"{BASE}/jobs", json={"tenant_id": "test", "payload": {}}).json()["status"] == "accepted"
def test_validation_empty(): assert r.post(f"{BASE}/jobs", json={"tenant_id": "", "payload": {}}).status_code == 422
def test_validation_special_chars(): assert r.post(f"{BASE}/jobs", json={"tenant_id": "a@#!", "payload": {}}).status_code == 422