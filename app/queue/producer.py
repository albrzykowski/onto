import json
import time

import pulsar

from app.config import PULSAR_URL
from app.logger import get_logger

logger = get_logger(__name__)

CONNECTION_TIMEOUT_SECONDS = 1
OPERATION_TIMEOUT_SECONDS = 2


class PulsarConnectionError(Exception):
    """Raised when Pulsar connection fails."""
    pass


class Producer:
    def __init__(self, retries=3):
        self.client = None
        self.producers = {}
        self.retries = retries

    def send(self, topic, msg):
        self._ensure_client()
        for attempt in range(self.retries):
            try:
                return self.get_producer(topic).send(json.dumps(msg).encode())
            except Exception as e:
                self._handle_send_error(e, attempt)
        raise PulsarConnectionError("Send failed after retries")

    def _ensure_client(self):
        if not self.client:
            try:
                self.client = pulsar.Client(
                    PULSAR_URL,
                    connection_timeout_ms=CONNECTION_TIMEOUT_SECONDS * 1000,
                    operation_timeout_seconds=OPERATION_TIMEOUT_SECONDS,
                )
            except Exception as e:
                logger.error(f"Pulsar connection failed: {e}")
                raise PulsarConnectionError(f"Pulsar connection failed: {e}") from e

    def _handle_send_error(self, e, attempt):
        if "connection" in str(e).lower() or "timeout" in str(e).lower():
            self._reconnect()
        if attempt < self.retries - 1:
            time.sleep(1)

    def _reconnect(self):
        try:
            self.client.close()
        except Exception:
            pass
        try:
            self.client = pulsar.Client(
                PULSAR_URL,
                connection_timeout_ms=CONNECTION_TIMEOUT_SECONDS * 1000,
                operation_timeout_seconds=OPERATION_TIMEOUT_SECONDS,
            )
        except Exception as conn_err:
            logger.error(f"Pulsar reconnection failed: {conn_err}")
            raise PulsarConnectionError(f"Pulsar connection failed: {conn_err}") from conn_err
        self.producers = {}

    def get_producer(self, topic):
        if topic not in self.producers:
            self.producers[topic] = self.client.create_producer(topic)
        return self.producers[topic]

    def close(self):
        if self.client:
            self.client.close()
