import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass
class LLMResponse:
    content: str
    success: bool
    error: str | None = None


class LLMProcessor:
    def __init__(self, api_key: str | None = None, model: str = "gpt-4.1-nano"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = OpenAI(api_key=self.api_key) if self.api_key else None

    async def process(self, text: str) -> LLMResponse:
        if not text:
            return LLMResponse(content="", success=False, error="Empty text")
        if not self._client:
            return LLMResponse(content="", success=False, error="OPENAI_API_KEY not set")

        try:
            response = self._client.responses.create(
                model=self.model,
                input=f"What is this text about?\n\n{text}"
            )
            return LLMResponse(content=response.output[0].content[0].text, success=True)
        except Exception as e:
            return LLMResponse(content="", success=False, error=str(e))