import os

PULSAR_URL = os.getenv("PULSAR_URL", "pulsar://localhost:6650")
PULSAR_ADMIN = os.getenv("PULSAR_ADMIN", "http://localhost:8080")
TOPIC_PREFIX = os.getenv("TOPIC_PREFIX", "persistent://public/default")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")