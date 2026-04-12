"""Async consumer for Pulsar."""
import json
import os
import urllib.request
from unittest.mock import AsyncMock

import pulsar
from openai import OpenAI

from app.config import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
    PULSAR_ADMIN,
    PULSAR_URL,
    QDRANT_HOST,
    QDRANT_PORT,
    TOPIC_PREFIX,
)
from app.logger import get_logger
from app.pipeline.llm_processor import LLMProcessor, LLMResponse
from app.resolver import (
    EntityResolver,
    PostgresRepo,
    QdrantClientWrapper,
    ResolverInput,
)

logger = get_logger(__name__)

MOCK_MODE = os.getenv("MOCK_LLM", "").lower() == "1"


def get_embedding(text: str) -> list[float]:
    """Generate embedding for text. Uses OpenAI text-embedding-3-small model."""
    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def mock_get_embedding(text: str) -> list[float]:
    """Mock embedding for testing. Returns fixed vector based on text hash."""
    hash_val = hash(text) % 1000
    base = hash_val / 1000.0
    return [base] * 1536


def get_embedding_fn():
    """Get embedding function based on MOCK_LLM flag."""
    if MOCK_MODE:
        return mock_get_embedding
    return get_embedding


class Consumer:
    def __init__(self, poll_interval: float = 0.1, max_iterations: int | None = None):
        self.client = None
        self.subscription = f"consumer-{os.getpid()}"
        self.consumers: dict = {}
        self.poll_interval = poll_interval
        self.max_iterations = max_iterations
        self._resolver: EntityResolver | None = None

    async def _get_resolver(self) -> EntityResolver:
        if self._resolver is None:
            qdrant = QdrantClientWrapper(host=QDRANT_HOST, port=QDRANT_PORT)
            postgres = PostgresRepo(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                database=POSTGRES_DB,
            )
            await postgres.connect()
            await postgres.init_schema()
            self._resolver = EntityResolver(
                qdrant_client=qdrant,
                postgres_repo=postgres,
                embedding_fn=get_embedding_fn(),
            )
            logger.info("EntityResolver initialized (mock=%s)", MOCK_MODE)
        return self._resolver

    def _get_processor(self) -> LLMProcessor:
        if MOCK_MODE:
            processor = LLMProcessor()
            processor.process = AsyncMock(return_value=self._mock_llm_response())
            logger.info("Using mock LLM processor")
            return processor
        return LLMProcessor()

    def _mock_llm_response(self):
        return LLMResponse(
            content={
                "entities": [
                    {"id": "E1", "label": "Poland", "type": "Location"},
                    {"id": "E2", "label": "Warsaw", "type": "Location"},
                ],
                "relations": [
                    {"subject": "E2", "predicate": "located_in", "object": "E1"},
                ],
            },
            success=True,
        )

    async def messages(self):
        if self.client is None:
            self.client = pulsar.Client(PULSAR_URL)
        await self._subscribe_topics()
        if self.max_iterations:
            for _ in range(self.max_iterations):
                await self._subscribe_topics()
                yield await self._consume_message()
        else:
            while True:
                await self._subscribe_topics()
                yield await self._consume_message()

    async def _subscribe_topics(self):
        for topic in self._topics():
            if topic not in self.consumers:
                self.consumers[topic] = self.client.subscribe(topic, self.subscription)

    async def _consume_message(self):
        for consumer in self.consumers.values():
            try:
                msg = consumer.receive(200)
                data = json.loads(msg.data())
                consumer.acknowledge(msg)
                return data
            except pulsar.Timeout:
                pass
            except Exception as e:
                logger.error(f"Err: {e}")
        return None

    def _topics(self):
        try:
            with urllib.request.urlopen(f"{PULSAR_ADMIN}/admin/v2/persistent/public/default", timeout=5) as r:
                return [t for t in json.loads(r.read()) if f"{TOPIC_PREFIX}/tenant-" in t]
        except Exception:
            return []

    async def _process_document(self, msg: dict, processor: LLMProcessor, resolver: EntityResolver):
        result = await processor.process(msg.get("content", ""))
        if not result.success:
            logger.error(f"LLM processing failed: {result.error}")
            return

        entities = result.content.get("entities", [])
        relations = result.content.get("relations", [])
        logger.info(f"Extracted {len(entities)} entities, {len(relations)} relations")

        if entities:
            await self._resolve_and_save(entities, relations, resolver)

    async def _resolve_and_save(self, entities: list, relations: list, resolver: EntityResolver):
        input_data = ResolverInput(entities=entities, relations=relations)
        output = await resolver.resolve(input_data)
        await self._save_relations(output, resolver.postgres)
        logger.info(f"Resolved to {len(output.decisions)} entities")

    async def _save_relations(self, output, postgres_repo: PostgresRepo):
        for rel in output.relations:
            await postgres_repo.insert_relation(
                subject_id=rel["subject"],
                predicate=rel["predicate"],
                object_id=rel["object"],
            )
        logger.info(f"Saved {len(output.relations)} relations")

    async def run(self):
        processor = self._get_processor()
        resolver = await self._get_resolver()
        async for msg in self.messages():
            if msg:
                logger.info(f"Processing document for tenant: {msg.get('tenant_id')}")
                await self._process_document(msg, processor, resolver)

    def close(self):
        if self.client:
            self.client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(Consumer().run())