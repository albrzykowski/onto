import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import QDRANT_HOST, QDRANT_PORT

logger = logging.getLogger(__name__)

COLLECTION_NAME = "entities"
VECTOR_SIZE = 1536


class QdrantClientWrapper:
    def __init__(self, host: str = QDRANT_HOST, port: int = QDRANT_PORT):
        self.client = QdrantClient(host=host, port=port)
        self._ensure_collection()

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]
        if COLLECTION_NAME not in names:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info(f"Created collection: {COLLECTION_NAME}")

    def search_similar(
        self,
        embedding: list[float],
        top_k: int = 5,
        entity_type: str | None = None,
    ) -> list[dict]:
        filter_condition = None
        if entity_type:
            filter_condition = {"must": [{"key": "entity_type", "match": {"value": entity_type}}]}

        response = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            limit=top_k,
            query_filter=filter_condition,
        )

        points = response.points if hasattr(response, 'points') else response

        return [
            {
                "id": r.id,
                "score": r.score,
                "label": r.payload.get("label"),
                "entity_type": r.payload.get("entity_type"),
                "canonical_id": r.payload.get("canonical_id"),
            }
            for r in points
        ]

    async def search_similar_async(
        self,
        embedding: list[float],
        top_k: int = 5,
        entity_type: str | None = None,
    ) -> list[dict]:
        return self.search_similar(embedding, top_k, entity_type)

    def _upsert(self, points: list[dict]):
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p.get("payload", {}),
                )
                for p in points
            ],
        )

    def insert_entity(self, entity_id: str, embedding: list[float], label: str, entity_type: str, canonical_id: str):
        self._upsert(
            points=[
                {
                    "id": entity_id,
                    "vector": embedding,
                    "payload": {
                        "label": label,
                        "entity_type": entity_type,
                        "canonical_id": canonical_id,
                    },
                }
            ],
        )

    async def update_canonical_id(self, entity_id: str, canonical_id: str):
        self.client.set_payload(
            collection_name=COLLECTION_NAME,
            points=[entity_id],
            payload={"canonical_id": canonical_id},
        )

    def upsert(self, collection_name: str, points: list[dict]):
        self._upsert(points)