"""Behave environment hooks."""

import subprocess
import time


def before_all(context):
    """Ensure Pulsar and API are running before all tests."""
    subprocess.run(["docker", "start", "pulsar-e2e"], capture_output=True)
    subprocess.run(["docker", "start", "api-e2e"], capture_output=True)
    _wait_for_pulsar_healthy()


def after_scenario(context, scenario):
    """Restart Pulsar and API after each scenario to ensure fresh connections."""
    subprocess.run(["docker", "stop", "pulsar-e2e"], capture_output=True)
    subprocess.run(["docker", "start", "pulsar-e2e"], capture_output=True)
    subprocess.run(["docker", "restart", "api-e2e"], capture_output=True)
    _wait_for_pulsar_healthy()
    time.sleep(2)


def _wait_for_pulsar_healthy(timeout=30):
    """Wait for Pulsar container to be healthy."""
    for _ in range(timeout):
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Health.Status}}", "pulsar-e2e"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "healthy" in result.stdout.strip().lower():
            return
        time.sleep(1)
