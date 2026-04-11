"""Unit tests for LLMProcessor."""
import pytest
from unittest.mock import MagicMock, patch

from app.pipeline.llm_processor import LLMProcessor, LLMResponse


class TestLLMResponse:
    def test_success_response(self):
        r = LLMResponse(content="test", success=True)
        assert r.content == "test"
        assert r.success is True
        assert r.error is None

    def test_error_response(self):
        r = LLMResponse(content="", success=False, error="error msg")
        assert r.content == ""
        assert r.success is False
        assert r.error == "error msg"


class TestLLMProcessor:
    def test_init_with_api_key(self):
        p = LLMProcessor(api_key="test-key")
        assert p.api_key == "test-key"

    def test_init_with_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        p = LLMProcessor()
        assert p.api_key == "env-key"

    def test_init_no_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = LLMProcessor()
        assert p.api_key is None

    @pytest.mark.asyncio
    async def test_process_empty_text(self):
        p = LLMProcessor(api_key="test")
        result = await p.process("")
        assert result == LLMResponse(content="", success=False, error="Empty text")

    @pytest.mark.asyncio
    async def test_process_no_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = LLMProcessor()
        result = await p.process("some text")
        assert result == LLMResponse(content="", success=False, error="OPENAI_API_KEY not set")

    @pytest.mark.asyncio
    async def test_process_success(self):
        mock_response = MagicMock()
        mock_response.output = [MagicMock(content=[MagicMock(text="summary text")])]

        with patch("app.pipeline.llm_processor.OpenAI") as mock_openai:
            mock_openai.return_value.responses.create = MagicMock(return_value=mock_response)
            p = LLMProcessor(api_key="test-key")
            result = await p.process("test content")

        assert result.success is True
        assert result.content == "summary text"

    @pytest.mark.asyncio
    async def test_process_exception(self):
        with patch("app.pipeline.llm_processor.OpenAI") as mock_openai:
            mock_openai.return_value.responses.create.side_effect = Exception("API error")
            p = LLMProcessor(api_key="test-key")
            result = await p.process("test content")

        assert result.success is False
        assert "API error" in result.error