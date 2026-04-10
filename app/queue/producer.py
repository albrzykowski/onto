"""Job producer."""
import json, time, pulsar
from app.config import PULSAR_URL
from app.logger import get_logger

logger = get_logger(__name__)

class Producer:
    def __init__(self, retries=3):
        self.client, self.prods, self.retries = None, {}, retries

    def send(self, topic, msg):
        if not self.client: self.client = pulsar.Client(PULSAR_URL)
        for _ in range(self.retries):
            try: return self._p(topic).send(json.dumps(msg).encode())
            except Exception as e:
                logger.warning(f"Fail: {e}")
                if "connection" in str(e).lower(): self.client = pulsar.Client(PULSAR_URL); self.prods = {}
                time.sleep(1)
        raise Exception("Send failed")

    def _p(self, t):
        if t not in self.prods: self.prods[t] = self.client.create_producer(t)
        return self.prods[t]

    def close(self): self.client and self.client.close()