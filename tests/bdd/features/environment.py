"""Behave environment hooks for BDD tests."""

import os
import subprocess
import time

# Path: /home/la/workspace/onto/tests/bdd/features/environment.py
# Need: /home/la/workspace/onto
_env_file = os.path.abspath(__file__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_env_file))))


def befor_all(context):
    # Clean everything first
    subprocess.run(
        ["docker-compose", "-f", "docker-compose.dev.yml", "down", "-v", "--remove-orphans"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    )
    
def before_scenario(context, scenario):
    """Start services before each scenario."""
    subprocess.run(
        ["docker-compose", "-f", "docker-compose.dev.yml", "up", "-d"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    )
    _wait_for_pulsar_healthy()


def after_scenario(context, scenario):
    """Cleanup after each scenario: stop, remove containers + volumes."""
    subprocess.run(
        ["docker-compose", "-f", "docker-compose.dev.yml", "down", "-v", "--remove-orphans"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    )


def _wait_for_pulsar_healthy(timeout: int = 60):
    """Wait for Pulsar to be healthy."""
    for _ in range(timeout):
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Health.Status}}", "pulsar-e2e"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if "healthy" in result.stdout.strip().lower():
            time.sleep(2)
            return
        time.sleep(1)
