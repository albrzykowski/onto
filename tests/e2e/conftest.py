"""E2E test configuration."""
import os
import socket
import sys
import time

import asyncpg
import pytest
import requests as r

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://localhost:8000"
ADMIN = "http://localhost:8080"
QDRANT = "http://localhost:6333"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432


def is_server_running(host="localhost", port=8000, timeout=1):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def is_pulsar_running(host="localhost", port=8080, timeout=1):
    try:
        response = r.get(f"http://{host}:{port}/admin/v2/clusters", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def is_qdrant_running(host="localhost", port=6333, timeout=1):
    try:
        response = r.get(f"http://{host}:{port}/collections", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def is_postgres_running(host="localhost", port=5432, timeout=1):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    if not is_server_running():
        skip = pytest.mark.skip(reason="API server not running")
        for item in items:
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def ensure_services():
    max_retries = 10
    for _ in range(max_retries):
        if is_server_running():
            break
        time.sleep(1)
    else:
        pytest.skip("API not available")


@pytest.fixture(scope="session")
def created_topics():
    topics = set()
    yield topics
    for topic in topics:
        try:
            r.delete(f"{ADMIN}/admin/v2/persistent/public/default/tenant-{topic}")
        except Exception:
            pass


@pytest.fixture(scope="module")
def precreated_topic(created_topics):
    topic = "e2e-test-topic"
    created_topics.add(topic)
    r.post(f"{BASE}/documents", json={"tenant_id": topic, "content": "init"})
    time.sleep(2)
    return topic


@pytest.fixture(scope="session")
async def postgres_pool():
    pool = await asyncpg.create_pool(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user="postgres",
        password="postgres",
        database="onto",
        min_size=2,
        max_size=10,
    )
    yield pool
    await pool.close()


@pytest.fixture
async def postgres_conn(postgres_pool):
    async with postgres_pool.acquire() as conn:
        yield conn