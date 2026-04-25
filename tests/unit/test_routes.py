"""Unit tests for routes."""
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.routes import create_document, health, ready
from app.schemas.document import DocumentRequest

STATUS_SERVICE_UNAVAILABLE = 503
STATUS_INTERNAL_SERVER_ERROR = 500


class TestHealth:
    def test_returns_healthy(self):
        # Given
        # When
        result = health()
        # Then
        assert result == {"status": "healthy"}


class TestReady:
    @patch("app.api.routes.socket.socket")
    def test_returns_ready(self, mock_socket):
        # Given
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.return_value = 0
        with patch("pulsar.Client"):
            # When
            result = ready()
            # Then
            assert result["status"] == "ready"

    @patch("app.api.routes.socket.socket")
    def test_returns_503_on_failure(self, mock_socket):
        # Given
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.return_value = 1
        # When
        try:
            ready()
        except HTTPException as e:
            # Then
            assert e.status_code == STATUS_SERVICE_UNAVAILABLE


class TestCreateDocument:
    @patch("app.api.routes.producer")
    def test_returns_accepted(self, mock_producer):
        # Given
        mock_producer.send.return_value = True
        doc = DocumentRequest(tenant_id="test", content="hello world")
        # When
        result = create_document(doc)
        # Then
        assert result["status"] == "queued"
        mock_producer.send.assert_called_once()

    @patch("app.api.routes.producer")
    def test_returns_500_on_error(self, mock_producer):
        # Given
        mock_producer.send.side_effect = Exception("fail")
        try:
            # When
            doc = DocumentRequest(tenant_id="test", content="hello world")
            create_document(doc)
        except HTTPException as e:
            # Then
            assert e.status_code == STATUS_INTERNAL_SERVER_ERROR