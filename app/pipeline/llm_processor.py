import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass
class LLMResponse:
    content: dict
    success: bool
    error: str | None = None


ONTOLOGY_PROMPT = """
You are an ontology learning system that extracts knowledge graphs from text.

Your task is to extract structured semantic information.

Return ONLY valid JSON. No explanations, no markdown, no extra text.

Schema:
{
  "entities": [
    {
      "id": "string",
      "label": "string",
      "type": "Person | Organization | Location | Event | Concept | Product | Other",
      "definition": "string describing the entity"
    }
  ],
  "relations": [
    {
      "subject": "entity_id",
      "predicate": "string",
      "object": "entity_id"
    }
  ]
}

Rules:
- Every entity must have a unique id (E1, E2, E3...)
- Use canonical labels (e.g. "OpenAI", not variants)
- Relations must reference entity IDs, not raw text
- Use simple predicates: works_for, located_in, part_of, uses, creates, causes, related_to, met
- Include a definition for each entity describing what it is
- If nothing is found, return empty lists
- Ensure JSON is valid and parsable

Text:
"""


class LLMProcessor:
    def __init__(self, api_key: str | None = None, model: str = "gpt-4.1-nano"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = OpenAI(api_key=self.api_key) if self.api_key else None

    async def process(self, text: str) -> LLMResponse:
        if not text:
            return LLMResponse(content={}, success=False, error="Empty text")

        if not self._client:
            return LLMResponse(content={}, success=False, error="OPENAI_API_KEY not set")

        try:
            response = self._client.responses.create(
                model=self.model,
                input=ONTOLOGY_PROMPT + text
            )

            raw = response.output[0].content[0].text

            data = json.loads(raw)

            return LLMResponse(content=data, success=True)

        except json.JSONDecodeError as e:
            return LLMResponse(content={}, success=False, error=f"Invalid JSON: {str(e)}")

        except Exception as e:
            return LLMResponse(content={}, success=False, error=str(e))
