import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def state() -> dict:
    """Mutable per-test state shared between step definitions."""
    return {"config": None, "error": None}


@pytest.fixture(autouse=True)
def isolate_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep scenarios independent of the developer's real API key."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Config file location, seeded with a minimal configuration."""
    path = tmp_path / "config.yaml"
    path.write_text("{}\n", encoding="utf-8")
    return path


@pytest.fixture
def config(state: dict):
    """The successfully loaded configuration."""
    assert state["error"] is None, f"loading failed: {state['error']!r}"
    return state["config"]
