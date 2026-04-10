"""Unit tests for producer."""
import json
from unittest.mock import patch, MagicMock
from app.queue.producer import QueueProducer


class TestConnect:
    def test_creates_pulsar_client(self):
        with patch("pulsar.Client") as mock:
            p = QueueProducer()
            p.connect()
            mock.assert_called_once()

    def test_raises_on_failure(self):
        with patch("pulsar.Client", side_effect=Exception("fail")):
            p = QueueProducer()
            try:
                p.connect()
            except Exception as e:
                assert str(e) == "fail"


class TestGetProducer:
    def test_creates_new_producer(self):
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            mock_client.return_value.create_producer.return_value = mock_producer
            p = QueueProducer()
            p.client = mock_client.return_value
            prod = p._get_producer("topic-test")
            assert prod == mock_producer
            mock_client.return_value.create_producer.assert_called_with("topic-test")

    def test_reuses_existing_producer(self):
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            p = QueueProducer()
            p.client = mock_client.return_value
            p.producers["topic-test"] = mock_producer
            prod = p._get_producer("topic-test")
            assert prod == mock_producer
            mock_client.return_value.create_producer.assert_not_called()


class TestSend:
    def test_encodes_json(self):
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            mock_client.return_value.create_producer.return_value = mock_producer
            p = QueueProducer()
            p.client = mock_client.return_value
            p.send("topic-test", {"key": "value"})
            call_args = mock_producer.send.call_args[0][0]
            assert json.loads(call_args) == {"key": "value"}

    def test_calls_connect_when_not_connected(self):
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            mock_client.return_value.create_producer.return_value = mock_producer
            p = QueueProducer()
            p.send("topic-test", {"test": 1})
            assert p.client is not None


class TestClose:
    def test_closes_client(self):
        with patch("pulsar.Client") as mock_client:
            p = QueueProducer()
            p.client = mock_client.return_value
            p.close()
            mock_client.return_value.close.assert_called_once()

    def test_handles_none_client(self):
        p = QueueProducer()
        p.close()  # Should not raise