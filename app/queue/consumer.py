"""Async consumer for Pulsar - logs received messages."""
import json
import os
import urllib.request

import pulsar

from app.config import PULSAR_ADMIN, PULSAR_URL, TOPIC_PREFIX
from app.logger import get_logger

logger = get_logger(__name__)


class Consumer:
    def __init__(
        self,
        poll_interval: float = 0.1,
        max_iterations: int | None = None,
    ):
        self.client = None
        self.subscription = f"consumer-{os.getpid()}"
        self.consumers: dict = {}
        self.poll_interval = poll_interval
        self.max_iterations = max_iterations

    async def messages(self):
        if self.client is None:
            self.client = pulsar.Client(PULSAR_URL)
        await self._subscribe_topics()
        if self.max_iterations:
            for _ in range(self.max_iterations):
                await self._subscribe_topics()
                yield await self._consume_message()
        else:
            while True:
                await self._subscribe_topics()
                yield await self._consume_message()

    async def _subscribe_topics(self):
        for topic in self._topics():
            if topic not in self.consumers:
                self.consumers[topic] = self.client.subscribe(topic, self.subscription)

    async def _consume_message(self):
        for consumer in self.consumers.values():
            try:
                msg = consumer.receive(200)
                data = json.loads(msg.data())
                consumer.acknowledge(msg)
                return data
            except pulsar.Timeout:
                pass
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
        return None

    def _topics(self):
        try:
            with urllib.request.urlopen(f"{PULSAR_ADMIN}/admin/v2/persistent/public/default", timeout=5) as r:
                return [t for t in json.loads(r.read()) if f"{TOPIC_PREFIX}/tenant-" in t]
        except Exception:
            return []

    async def run(self):
        async for msg in self.messages():
            if msg:
                logger.info(f"Received: {msg}")

    def close(self):
        if self.client:
            self.client.close()