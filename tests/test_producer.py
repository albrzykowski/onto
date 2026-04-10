"""Unit tests for producer."""
import json
from unittest.mock import patch, MagicMock
from app.queue.producer import Producer


class TestSend:
    def test_encodes_json(self):
        # Given
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            mock_client.return_value.create_producer.return_value = mock_producer
            p = Producer()
            p.client = mock_client.return_value

            # When
            p.send("topic-test", {"key": "value"})

            # Then
            call_args = mock_producer.send.call_args[0][0]
            assert json.loads(call_args) == {"key": "value"}

    def test_calls_connect_when_not_connected(self):
        # Given
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            mock_client.return_value.create_producer.return_value = mock_producer
            p = Producer()

            # When
            p.send("topic-test", {"test": 1})

            # Then
            assert p.client is not None


class TestGetProducer:
    def test_creates_new_producer(self):
        # Given
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            mock_client.return_value.create_producer.return_value = mock_producer
            p = Producer()
            p.client = mock_client.return_value

            # When
            prod = p._get_producer("topic-test")

            # Then
            assert prod == mock_producer
            mock_client.return_value.create_producer.assert_called_with("topic-test")

    def test_reuses_existing_producer(self):
        # Given
        with patch("pulsar.Client") as mock_client:
            mock_producer = MagicMock()
            p = Producer()
            p.client = mock_client.return_value
            p.producers["topic-test"] = mock_producer

            # When
            prod = p._get_producer("topic-test")

            # Then
            assert prod == mock_producer
            mock_client.return_value.create_producer.assert_not_called()


class TestClose:
    def test_closes_client(self):
        # Given
        with patch("pulsar.Client") as mock_client:
            p = Producer()
            p.client = mock_client.return_value

            # When
            p.close()

            # Then
            mock_client.return_value.close.assert_called_once()

    def test_handles_none_client(self):
        # Given
        p = Producer()

        # When
        # Then
        p.close()