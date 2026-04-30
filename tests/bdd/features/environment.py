"""Behave environment hooks for BDD tests."""

import os
import subprocess
import time

_env_file = os.path.abspath(__file__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_env_file))))


def before_all(context):
    """Clean up Docker before all tests."""
    subprocess.run(
        ["docker-compose", "-f", "docker-compose.dev.yml", "down", "-v", "--remove-orphans"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def before_scenario(context, scenario):
    """Start services before each scenario."""
    result = subprocess.run(
        ["docker-compose", "-f", "docker-compose.dev.yml", "up", "-d"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Docker compose up failed: {result.stderr}")
    _wait_for_services_ready()


def after_scenario(context, scenario):
    """Cleanup after each scenario: stop, remove containers + volumes."""
    result = subprocess.run(
        ["docker-compose", "-f", "docker-compose.dev.yml", "down", "-v", "--remove-orphans"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Docker compose down failed: {result.stderr}")


def _wait_for_services_ready(timeout: int = 60):
    """Wait for Pulsar and API to be ready."""
    # Wait for Pulsar healthy
    for _ in range(timeout):
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Health.Status}}", "pulsar-e2e"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "healthy" in result.stdout.strip().lower():
            break
        time.sleep(1)
    else:
        print("Pulsar did not become healthy in time")
        return

    # Wait for Pulsar broker port
    for _ in range(10):
        try:
            s = __import__('socket').socket()
            s.settimeout(1)
            s.connect(('localhost', 6650))
            s.close()
            break
        except Exception:
            time.sleep(1)
    else:
        print("Pulsar broker port not ready in time")

    # Wait for API to be ready
    import requests
    for _ in range(30):
        try:
            resp = requests.get("http://localhost:8000/health", timeout=2)
            if resp.status_code == 200:
                time.sleep(1)
                return
        except Exception:
            pass
        time.sleep(1)
    print("API did not become ready in time")
