import os

PULSAR_URL = os.getenv("PULSAR_URL", "pulsar://localhost:6650")
PULSAR_ADMIN = os.getenv("PULSAR_ADMIN", "http://localhost:8080")
TOPIC_PREFIX = os.getenv("TOPIC_PREFIX", "persistent://public/default")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000") or 8000)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333") or 6333)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432") or 5432)
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "onto")