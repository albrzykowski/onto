"""Unit tests for producer."""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.queue.producer import Producer

EXPECTED_RETRY_COUNT = 3


class TestProducer:
    @patch("pulsar.Client")
    def test_send_encodes_json(self, mock_pulsar_client):
        # Given
        mock_producer = MagicMock()
        mock_pulsar_client.return_value.create_producer.return_value = mock_producer

        p = Producer()
        p.client = mock_pulsar_client.return_value

        # When
        result = p.send("topic-test", {"key": "value"})

        # Then
        call_args = mock_producer.send.call_args[0][0]
        assert json.loads(call_args) == {"key": "value"}
        assert result is not None

    @patch("pulsar.Client")
    def test_send_creates_client_when_not_connected(self, mock_pulsar_client):
        # Given
        mock_producer = MagicMock()
        mock_pulsar_client.return_value.create_producer.return_value = mock_producer

        p = Producer()

        # When
        p.send("topic-test", {"test": 1})

        # Then
        assert p.client is not None

    @patch("time.sleep")
    @patch("pulsar.Client")
    def test_send_retries_on_failure(self, mock_pulsar_client, mock_sleep):
        # Given
        mock_producer = MagicMock()
        mock_producer.send.side_effect = [Exception("fail"), Exception("fail"), MagicMock()]
        mock_pulsar_client.return_value.create_producer.return_value = mock_producer

        p = Producer()
        p.client = mock_pulsar_client.return_value

        # When
        result = p.send("topic-test", {"test": 1})

        # Then
        assert mock_producer.send.call_count == EXPECTED_RETRY_COUNT
        assert result is not None

    @patch("time.sleep")
    @patch("pulsar.Client")
    def test_send_raises_after_max_retries(self, mock_pulsar_client, mock_sleep):
        # Given
        mock_producer = MagicMock()
        mock_producer.send.side_effect = Exception("fail")
        mock_pulsar_client.return_value.create_producer.return_value = mock_producer

        p = Producer()
        p.client = mock_pulsar_client.return_value

        # When # Then
        with pytest.raises(Exception) as exc_info:
            p.send("topic-test", {"test": 1})
        assert "failed" in str(exc_info.value).lower()
        assert mock_sleep.call_count == EXPECTED_RETRY_COUNT - 1

    @patch("pulsar.Client")
    def test_get_producer_creates_new(self, mock_pulsar_client):
        # Given
        mock_producer = MagicMock()
        mock_pulsar_client.return_value.create_producer.return_value = mock_producer

        p = Producer()
        p.client = mock_pulsar_client.return_value

        # When
        prod = p.get_producer("topic-test")

        # Then
        assert prod == mock_producer
        mock_pulsar_client.return_value.create_producer.assert_called_with("topic-test")

    @patch("pulsar.Client")
    def test_get_producer_reuses_existing(self, mock_pulsar_client):
        # Given
        mock_producer = MagicMock()
        p = Producer()
        p.client = mock_pulsar_client.return_value
        p.producers["topic-test"] = mock_producer

        # When
        prod = p.get_producer("topic-test")

        # Then
        assert prod == mock_producer
        mock_pulsar_client.return_value.create_producer.assert_not_called()

    @patch("pulsar.Client")
    def test_close_closes_client(self, mock_pulsar_client):
        # Given
        p = Producer()
        p.client = mock_pulsar_client.return_value

        # When
        p.close()

        # Then
        mock_pulsar_client.return_value.close.assert_called_once()

    def test_close_handles_none_client(self):
        # Given
        p = Producer()

        # When
        p.close()

        # Then
        # Should not raise