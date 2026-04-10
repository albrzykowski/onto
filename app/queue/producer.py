import json
import pulsar


class QueueProducer:
    def __init__(self):
        self.client = pulsar.Client("pulsar://localhost:6650")
        self.producers = {}

    def _get_producer(self, topic: str):
        if topic not in self.producers:
            self.producers[topic] = self.client.create_producer(topic)
        return self.producers[topic]

    def send(self, topic: str, message: dict):
        producer = self._get_producer(topic)

        producer.send(
            json.dumps(message).encode("utf-8")
        )
