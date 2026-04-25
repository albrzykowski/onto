import logging
from collections.abc import Callable

from app.resolver.qdrant_client import QdrantClientWrapper

logger = logging.getLogger(__name__)

DEFAULT_CANDIDATE_LIMIT = 5


class RetrievalResult:
    def __init__(self, candidates: list[dict]):
        self.candidates = candidates

    def to_list(self) -> list[dict]:
        return self.candidates

    def is_empty(self) -> bool:
        return len(self.candidates) == 0

    def count(self) -> int:
        return len(self.candidates)

    def first(self) -> dict | None:
        return self.candidates[0] if self.candidates else None


class EntityRetrieval:
    def __init__(
        self,
        qdrant_client: QdrantClientWrapper,
        embedding_fn: Callable[[str], list[float]],
        default_limit: int = DEFAULT_CANDIDATE_LIMIT,
    ):
        self.qdrant = qdrant_client
        self.embedding_fn = embedding_fn
        self.default_limit = default_limit

    async def retrieve(
        self,
        query: str,
        entity_type: str | None = None,
        limit: int | None = None,
    ) -> RetrievalResult:
        if not query:
            logger.warning("Empty query provided to retrieval")
            return RetrievalResult(candidates=[])

        try:
            embedding = self.embedding_fn(query)
        except Exception as e:
            logger.error(f"Failed to generate embedding for query '{query}': {e}")
            return RetrievalResult(candidates=[])

        top_k = limit if limit is not None else self.default_limit

        try:
            candidates = self.qdrant.search_similar(
                embedding=embedding,
                top_k=top_k,
                entity_type=entity_type,
            )
            return RetrievalResult(candidates=candidates)
        except Exception as e:
            logger.error(f"Vector store search failed: {e}")
            return RetrievalResult(candidates=[])

    async def retrieve_by_embedding(
        self,
        embedding: list[float],
        entity_type: str | None = None,
        limit: int | None = None,
    ) -> RetrievalResult:
        top_k = limit if limit is not None else self.default_limit

        try:
            candidates = self.qdrant.search_similar(
                embedding=embedding,
                top_k=top_k,
                entity_type=entity_type,
            )
            return RetrievalResult(candidates=candidates)
        except Exception as e:
            logger.error(f"Vector store search failed: {e}")
            return RetrievalResult(candidates=[])