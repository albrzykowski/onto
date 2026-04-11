import os
from dataclasses import dataclass

from openai import OpenAI

from app.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingResult:
    tenant_id: str
    content: str
    summary: str
    success: bool
    error: str | None = None


class OntologyPipeline:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    async def process(self, msg: dict) -> ProcessingResult:
        tenant_id = msg.get("tenant_id", "unknown")
        content = msg.get("content", "")

        if not content or not self.client:
            return ProcessingResult(
                tenant_id=tenant_id,
                content=content,
                summary="",
                success=False,
                error="Empty content" if not content else "OPENAI_API_KEY not configured"
            )

        response = self.client.responses.create(
            model="gpt-4.1-nano",
            input=f"What is this text about?\n\n{content}"
        )
        return ProcessingResult(
            tenant_id=tenant_id,
            content=content,
            summary=response.output[0].content[0].text,
            success=True
        )