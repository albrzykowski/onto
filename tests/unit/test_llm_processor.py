"""Unit tests for LLMProcessor."""
import pytest

from app.pipeline.llm_processor import LLMProcessor, LLMResponse


class TestLLMResponse:
    def test_success_response(self):
        # Given
        r = LLMResponse(content="test", success=True)
        # When
        # Then
        assert r.content == "test"
        assert r.success is True
        assert r.error is None

    def test_error_response(self):
        # Given
        r = LLMResponse(content="", success=False, error="error msg")
        # When
        # Then
        assert r.content == ""
        assert r.success is False
        assert r.error == "error msg"


class TestLLMProcessor:
    def test_init_with_api_key(self):
        # Given
        # When
        p = LLMProcessor(api_key="test-key")
        # Then
        assert p.api_key == "test-key"

    def test_init_with_env_var(self, monkeypatch):
        # Given
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        # When
        p = LLMProcessor()
        # Then
        assert p.api_key == "env-key"

    def test_init_no_api_key(self, monkeypatch):
        # Given
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # When
        p = LLMProcessor()
        # Then
        assert p.api_key is None

    @pytest.mark.asyncio
    async def test_process_empty_text(self, monkeypatch):
        # Given
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = LLMProcessor(api_key="test")
        # When
        result = await p.process("")
        # Then
        assert result == LLMResponse(content={}, success=False, error="Empty text")

    @pytest.mark.asyncio
    async def test_process_no_api_key(self, monkeypatch):
        # Given
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = LLMProcessor()
        # When
        result = await p.process("some text")
        # Then
        assert result == LLMResponse(content={}, success=False, error="OPENAI_API_KEY not set")