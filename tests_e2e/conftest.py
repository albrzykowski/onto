"""E2E test configuration - auto-skip if services not available."""
import os
import socket
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def is_server_running(host="localhost", port=8000, timeout=1):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except: return False


def pytest_collection_modifyitems(config, items):
    if not is_server_running():
        skip = pytest.mark.skip(reason="Server not running. Run: python -m app.main")
        for item in items:
            item.add_marker(skip)