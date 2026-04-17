"""BDD Test Configuration."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "document: Document submission scenarios")
    config.addinivalue_line("markers", "health: Health monitoring scenarios")
    config.addinivalue_line("markers", "extraction: Entity extraction scenarios")
    config.addinivalue_line("markers", "resolution: Entity resolution scenarios")
    config.addinivalue_line("markers", "integration: End-to-end integration scenarios")


@pytest.fixture
def api_base_url():
    """Base URL for API tests."""
    return "http://localhost:8000"


@pytest.fixture
def tenant_id():
    """Default tenant ID for tests."""
    return "test-tenant"


@pytest.fixture
def sample_content():
    """Sample document content for tests."""
    return "John works at Acme Corp as a software engineer in San Francisco."
