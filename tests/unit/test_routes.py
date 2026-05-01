"""Unit tests for routes."""
import socket
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes import create_document, health, ready
from app.schemas.document import DocumentRequest


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

    def test_returns_503_on_failure(self):
        # Given
        real_socket = socket.socket

        class FailingSocket:
            def settimeout(self, x): pass
            def connect_ex(self, x): return 1
            def connect(self, x): raise OSError("Connection refused")
            def close(self): pass

        socket.socket = lambda *a, **kw: FailingSocket()

        try:
            # When # Then
            with pytest.raises(HTTPException) as exc_info:
                ready()
            assert exc_info.value.status_code == 503
        finally:
            socket.socket = real_socket


class TestCreateDocument:
    @patch("app.api.routes.producer")
    def test_returns_accepted(self, mock_producer):
        # Given
        mock_producer.send.return_value = True
        doc = DocumentRequest(tenant_id="test", content="hello world")
        # When
        result = create_document(doc)
        # Then
        assert result["status"] == "accepted"
        mock_producer.send.assert_called_once()

    @patch("app.api.routes.producer")
    def test_returns_500_on_error(self, mock_producer):
        # Given
        mock_producer.send.side_effect = Exception("fail")
        doc = DocumentRequest(tenant_id="test", content="hello world")
        # When # Then
        with pytest.raises(HTTPException) as exc_info:
            create_document(doc)
        assert exc_info.value.status_code == 500