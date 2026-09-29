import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def state() -> dict:
    """Mutable per-test state shared between step definitions."""
    return {"candidates": [], "chunks": [], "config": None, "error": None, "records": []}


@pytest.fixture(autouse=True)
def isolate_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep scenarios independent of the developer's real API key.

    BuilderConfig always requires an API key, so scenarios that build a
    configuration get a dummy one; the scenarios about a missing key delete it
    explicitly.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")


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


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated working directory, so steps can use relative paths."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def output_dir(workdir: Path) -> Path:
    """Directory a build writes the ontology to."""
    return workdir / "ontology"


@pytest.fixture
def provenance_path(output_dir: Path) -> Path:
    """Location of the JSONL provenance log a build writes."""
    return output_dir / "provenance.jsonl"


@pytest.fixture
def schema_path(output_dir: Path) -> Path:
    """Location of the LinkML T-Box a build writes."""
    return output_dir / "schema.yaml"
