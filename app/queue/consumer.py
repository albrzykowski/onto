"""Async consumer for Pulsar."""
import json
import os
import urllib.request

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
from app.pipeline.llm_processor import LLMProcessor
from app.resolver import (
    EntityResolver,
    PostgresRepo,
    QdrantClientWrapper,
    ResolverInput,
)

logger = get_logger(__name__)


def get_embedding(text: str) -> list[float]:
    """Generate embedding for text. Uses OpenAI text-embedding-3-small model."""
    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


class Consumer:
    def __init__(
        self,
        poll_interval: float = 0.1,
        max_iterations: int | None = None,
        embedding_fn=None,
        processor_class=None,
    ):
        self.client = None
        self.subscription = f"consumer-{os.getpid()}"
        self.consumers: dict = {}
        self.poll_interval = poll_interval
        self.max_iterations = max_iterations
        self._resolver: EntityResolver | None = None
        self._embedding_fn = embedding_fn or get_embedding
        self._processor_class = processor_class or LLMProcessor

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
                embedding_fn=self._embedding_fn,
            )
        return self._resolver

    def _get_processor(self) -> LLMProcessor:
        return self._processor_class()

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
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock LLM processor")
    args = parser.parse_args()

    kwargs = {}
    if args.mock:
        from tests_e2e.fixtures import MockLLMProcessor, mock_get_embedding
        kwargs["embedding_fn"] = mock_get_embedding
        kwargs["processor_class"] = MockLLMProcessor

    asyncio.run(Consumer(**kwargs).run())