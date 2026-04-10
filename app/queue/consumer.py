import json
import os
import time
import urllib.request

import pulsar

from app.config import PULSAR_ADMIN, PULSAR_URL, TOPIC_PREFIX
from app.logger import get_logger

logger = get_logger(__name__)

class Consumer:
    def __init__(self, interval=5):
        self.client, self.subscription, self.consumers, self.interval = None, f"consumer-{os.getpid()}", {}, interval

    def run(self):
        self.client = pulsar.Client(PULSAR_URL)
        while True:
            self._subscribe_topics()
            self._consume_messages()
            time.sleep(0.1)

    def _subscribe_topics(self):
        for topic in self._topics():
            if topic not in self.consumers:
                self.consumers[topic] = self.client.subscribe(topic, self.subscription)

    def _consume_messages(self):
        for consumer in self.consumers.values():
            try:
                msg = consumer.receive(1000)
                self._process(json.loads(msg.data()))
                consumer.acknowledge(msg)
            except pulsar.Timeout:
                pass
            except Exception as e:
                logger.error(f"Err: {e}")

    def _topics(self):
        try:
            with urllib.request.urlopen(f"{PULSAR_ADMIN}/admin/v2/persistent/public/default", timeout=5) as r:
                return [t for t in json.loads(r.read()) if f"{TOPIC_PREFIX}/tenant-" in t]
        except: return []

    def _process(self, data): logger.info(f"Job: {data.get('job_id')} for {data.get('tenant_id')}")
