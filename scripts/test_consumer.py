"""Test runner that starts consumer with mocks."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.mocks import mock_fixtures
from app.queue.consumer import Consumer

asyncio.run(Consumer(
    embedding_fn=mock_fixtures.mock_get_embedding,
    processor_class=mock_fixtures.MockLLMProcessor
).run())
