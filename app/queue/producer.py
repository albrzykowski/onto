"""Job producer - minimal."""
import json, time, pulsar
from app.config import PULSAR_URL
from app.logger import get_logger

logger = get_logger(__name__)


class QueueProducer:
    def __init__(self, retries=3):
        self.client = None
        self.producers = {}
        self.retries = retries

    def connect(self):
        self.client = pulsar.Client(PULSAR_URL)

    def _get_producer(self, topic):
        if topic not in self.producers:
            self.producers[topic] = self.client.create_producer(topic)
        return self.producers[topic]

    def send(self, topic, msg):
        if not self.client:
            self.connect()
        for _ in range(self.retries):
            try:
                self._get_producer(topic).send(json.dumps(msg).encode())
                return True
            except Exception as e:
                logger.warning(f"Failed: {e}")
                if "connection" in str(e).lower():
                    self.client = pulsar.Client(PULSAR_URL)
                    self.producers = {}
                time.sleep(1)
        raise Exception("Send failed")

    def close(self):
        if self.client:
            self.client.close()