import json
import time

import pulsar

from app.config import PULSAR_URL
from app.logger import get_logger

logger = get_logger(__name__)

class Producer:
    def __init__(self, retries=3):
        self.client = None
        self.producers = {}
        self.retries = retries

    def send(self, topic, msg):
        if not self.client:
            self.client = pulsar.Client(PULSAR_URL)
        for _ in range(self.retries):
            try:
                return self.get_producer(topic).send(json.dumps(msg).encode())
            except Exception as e:
                logger.warning(f"Fail: {e}")
                if "connection" in str(e).lower():
                    self.client = pulsar.Client(PULSAR_URL)
                    self.producers = {}
                time.sleep(1)
        raise Exception("Send failed")

    def get_producer(self, topic):
        if topic not in self.producers:
            self.producers[topic] = self.client.create_producer(topic)
        return self.producers[topic]

    def close(self):
        if self.client:
            self.client.close()
