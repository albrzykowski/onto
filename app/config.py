import os

PULSAR_URL = os.getenv("PULSAR_URL", "pulsar://localhost:6650")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")