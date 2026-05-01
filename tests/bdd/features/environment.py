"""Behave environment hooks for BDD tests."""

import os
import socket
import subprocess
import time

import requests

# PROJECT_ROOT is 4 levels up from this file: tests/bdd/features/environment.py -> /home/la/workspace/onto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _run_docker_compose(command):
    """Run docker compose command with proper file path."""
    result = subprocess.run(
        ["docker", "compose", "-f", f"{PROJECT_ROOT}/docker-compose.dev.yml"] + command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result


def before_all(context):
    """Clean up Docker before all tests."""
    _run_docker_compose(["down", "-v", "--remove-orphans"])


def before_scenario(context, scenario):
    """Start services before each scenario."""
    print(f"Starting services for scenario: {scenario.name}")
    result = _run_docker_compose(["up", "-d"])
    if result.returncode != 0:
        print(f"Docker compose up failed: {result.stderr}")
        return
    print("Services started, waiting for readiness...")
    try:
        _wait_for_services_ready()
        print("Services ready!")
    except AssertionError as e:
        print(f"Services failed to start: {e}")
        raise


def after_scenario(context, scenario):
    """Cleanup after each scenario: stop, remove containers + volumes."""
    result = _run_docker_compose(["down", "-v", "--remove-orphans"])
    if result.returncode != 0:
        print(f"Docker compose down failed: {result.stderr}")


def _wait_for_services_ready(timeout: int = 60):  # noqa: PLR0915
    """Wait for Pulsar and API to be ready."""
    # Wait for Pulsar healthy
    for i in range(timeout):
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Health.Status}}", "pulsar-dev"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if "healthy" in result.stdout.strip().lower():
            print(f"Pulsar healthy after {i} seconds")
            break
        time.sleep(1)
    else:
        # Print debug info before failing
        result = subprocess.run(
            ["docker", "logs", "pulsar-dev"],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"Pulsar logs: {result.stdout[-500:] if result.stdout else 'None'}")
        raise AssertionError("Pulsar did not become healthy in time")

    # Wait for Pulsar broker port
    for _ in range(10):
        try:
            s = socket.socket()
            s.settimeout(1)
            s.connect(('localhost', 6650))
            s.close()
            break
        except Exception:
            time.sleep(1)
    else:
        raise AssertionError("Pulsar broker port not ready in time")

    # Wait for API to be ready
    for i in range(30):
        try:
            resp = requests.get("http://localhost:8000/health", timeout=2)
            if resp.status_code == 200:
                print(f"API ready after {i} seconds")
                time.sleep(1)
                return
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError("API did not become ready in time")
