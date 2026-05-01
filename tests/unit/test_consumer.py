"""Unit tests for async consumer."""
import asyncio
from unittest.mock import MagicMock, patch

import pulsar

from app.queue.consumer import Consumer


class MockMessage:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


async def collect_messages(consumer, limit):
    """Collect messages from consumer async generator."""
    msgs = []
    count = 0
    async for msg in consumer.messages():
        if msg is not None:
            msgs.append(msg)
            count += 1
        if count >= limit:
            break
    return msgs


class TestConsumer:
    @patch("app.queue.consumer.pulsar.Client")
    def test_messages_yields_messages(self, mock_pulsar_client):
        # Given
        mock_consumer = MagicMock()
        mock_consumer.receive.return_value = MockMessage(
            b'{"job_id": "123", "tenant_id": "tenant-a"}'
        )
        mock_pulsar_client.return_value.subscribe.return_value = mock_consumer
        c = Consumer(poll_interval=0, max_iterations=1)
        c._topics = MagicMock(return_value=["persistent://public/default/tenant-a"])

        # When
        messages = asyncio.run(collect_messages(c, 1))

        # Then
        assert len(messages) == 1
        assert messages[0]["job_id"] == "123"

    @patch("app.queue.consumer.pulsar.Client")
    def test_messages_handles_timeout(self, mock_pulsar_client):
        # Given
        mock_consumer = MagicMock()
        mock_consumer.receive.side_effect = pulsar.Timeout()
        mock_pulsar_client.return_value.subscribe.return_value = mock_consumer
        c = Consumer(poll_interval=0, max_iterations=1)
        c._topics = MagicMock(return_value=["persistent://public/default/tenant-a"])

        # When
        messages = asyncio.run(collect_messages(c, 1))

        # Then
        assert len(messages) == 0

    @patch("app.queue.consumer.pulsar.Client")
    def test_run_logs_messages(self, mock_pulsar_client):
        # Given
        mock_consumer = MagicMock()
        mock_consumer.receive.return_value = MockMessage(
            b'{"job_id": "123", "tenant_id": "tenant-a"}'
        )
        mock_pulsar_client.return_value.subscribe.return_value = mock_consumer
        c = Consumer(poll_interval=0, max_iterations=1)
        c._topics = MagicMock(return_value=["persistent://public/default/tenant-a"])

        with patch("app.queue.consumer.logger") as mock_log:
            # When
            asyncio.run(c.run())

            # Then
            mock_log.info.assert_called()

    def test_close(self):
        # Given
        c = Consumer()
        c.client = MagicMock()

        # When
        c.close()

        # Then
        c.client.close.assert_called_once()

    def test_close_handles_none_client(self):
        # Given
        c = Consumer()

        # When # Then
        c.close()  # Should not raise