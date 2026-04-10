"""Unit tests for consumer."""
import json
from unittest.mock import MagicMock, patch

from app.queue.consumer import Consumer

EXPECTED_TENANT_COUNT = 2


class TestDiscoverTopics:
    def test_returns_tenant_topics(self):
        # Given
        topics = ["persistent://public/default/tenant-a", "persistent://public/default/tenant-b"]
        with patch("urllib.request.urlopen") as mock:
            mock.return_value.__enter__ = MagicMock(return_value=MagicMock(read=lambda: json.dumps(topics)))
            mock.return_value.__exit__ = MagicMock(return_value=False)

            # When
            c = Consumer()
            result = c._topics()

            # Then
            assert result == topics

    def test_returns_empty_on_error(self):
        # Given
        with patch("urllib.request.urlopen", side_effect=Exception("no network")):
            # When
            c = Consumer()
            result = c._topics()

            # Then
            assert result == []


class TestProcess:
    def test_logs_job_info(self):
        # Given
        data = {"job_id": "123", "tenant_id": "tenant-a", "payload": {"task": "test"}}
        with patch("app.queue.consumer.logger") as mock_log:
            # When
            c = Consumer()
            c._process(data)

            # Then
            mock_log.info.assert_called_once()


class TestTopicFiltering:
    def test_filters_non_tenant_topics(self):
        # Given
        topics = [
            "persistent://public/default/tenant-a",
            "persistent://public/default/other-topic",
            "persistent://public/default/tenant-b",
        ]
        with patch("urllib.request.urlopen") as mock:
            mock.return_value.__enter__ = MagicMock(return_value=MagicMock(read=lambda: json.dumps(topics)))
            mock.return_value.__exit__ = MagicMock(return_value=False)

            # When
            c = Consumer()
            result = c._topics()

            # Then
            assert "persistent://public/default/other-topic" not in result
            assert len(result) == EXPECTED_TENANT_COUNT