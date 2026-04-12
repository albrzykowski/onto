import logging
import uuid
from collections.abc import Callable

from app.resolver.models import (
    EntityDict,
    EntityType,
    RelationDict,
    ResolutionAction,
    ResolutionDecision,
    ResolverInput,
    ResolverOutput,
)
from app.resolver.postgres_repo import PostgresRepo
from app.resolver.qdrant_client import QdrantClientWrapper

logger = logging.getLogger(__name__)

DEFAULT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_TOP_K = 5


class EntityResolver:
    def __init__(
        self,
        qdrant_client: QdrantClientWrapper,
        postgres_repo: PostgresRepo,
        embedding_fn: Callable[[str], list[float]],
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
    ):
        self.qdrant = qdrant_client
        self.postgres = postgres_repo
        self.embedding_fn = embedding_fn
        self.confidence_threshold = confidence_threshold
        self.top_k = top_k

    async def resolve(self, input_data: ResolverInput) -> ResolverOutput:
        decisions = []
        canonical_id_map = {}
        for entity_dict in input_data.entities:
            decision = await self._resolve_entity(entity_dict)
            decisions.append(decision)
            canonical_id_map[entity_dict["id"]] = decision.canonical_entity_id

        mapped_relations = self._map_relations(input_data.relations, canonical_id_map)
        return ResolverOutput(decisions=decisions, relations=mapped_relations)

    async def _resolve_entity(self, entity_dict: EntityDict) -> ResolutionDecision:
        label = entity_dict["label"]
        entity_type = self._parse_entity_type(entity_dict["type"])
        embedding = self._get_embedding(label)

        if embedding is None:
            return self._create_decision(ResolutionAction.CREATE_NEW, str(uuid.uuid4()), 0.0)

        candidates = await self._search_candidates(embedding, entity_type)

        if not candidates:
            return await self._create_new_entity(label, entity_type, embedding, 1.0)

        final_score = self._calculate_score(candidates[0], entity_type)

        if final_score >= self.confidence_threshold:
            return await self._merge_entity(candidates[0], final_score)

        return await self._create_new_entity(label, entity_type, embedding, final_score)

    def _parse_entity_type(self, entity_type_str: str) -> EntityType:
        return EntityType(entity_type_str) if entity_type_str in EntityType.__members__ else EntityType.OTHER

    def _get_embedding(self, label: str) -> list[float] | None:
        try:
            return self.embedding_fn(label)
        except Exception as e:
            logger.error(f"Failed to generate embedding for {label}: {e}")
            return None

    async def _search_candidates(self, embedding: list[float], entity_type: EntityType) -> list[dict]:
        try:
            return await self.qdrant.search_similar(
                embedding=embedding,
                top_k=self.top_k,
                entity_type=entity_type,
            )
        except Exception as e:
            logger.warning(f"Qdrant search failed, creating new entity: {e}")
            return []

    def _calculate_score(self, candidate: dict, entity_type: EntityType) -> float:
        base_score = candidate["score"]
        type_match = candidate.get("entity_type") == entity_type.value
        return base_score - (0.1 if not type_match else 0.0)

    async def _create_new_entity(self, label: str, entity_type: EntityType, embedding: list[float], confidence: float) -> ResolutionDecision:
        canonical_id = str(uuid.uuid4())
        entity_id = await self.postgres.insert_entity(
            canonical_id=canonical_id,
            label=label,
            entity_type=entity_type,
        )
        try:
            await self.qdrant.insert_entity(
                entity_id=entity_id,
                embedding=embedding,
                label=label,
                entity_type=entity_type,
                canonical_id=canonical_id,
            )
        except Exception as e:
            logger.error(f"Failed to index in Qdrant: {e}")

        return self._create_decision(ResolutionAction.CREATE_NEW, canonical_id, confidence)

    async def _merge_entity(self, candidate: dict, score: float) -> ResolutionDecision:
        canonical_id = candidate["canonical_id"]
        db_entity = await self.postgres.get_canonical_entity_by_id(candidate["id"])

        if db_entity:
            canonical_id = db_entity["canonical_id"]

        await self.postgres.record_merge(canonical_entity_id=canonical_id, merged_entity_id=candidate["id"])
        await self.postgres.update_canonical_id(candidate["id"], canonical_id)

        try:
            await self.qdrant.update_canonical_id(candidate["id"], canonical_id)
        except Exception as e:
            logger.error(f"Failed to update Qdrant: {e}")

        return self._create_decision(ResolutionAction.MERGE, canonical_id, float(score), [candidate["id"]])

    def _create_decision(self, action: ResolutionAction, canonical_id: str, confidence: float, merged_with: list = None) -> ResolutionDecision:
        return ResolutionDecision(
            action=action,
            canonical_entity_id=canonical_id,
            confidence=confidence,
            merged_with=merged_with or [],
        )

    def _map_relations(self, relations: list[RelationDict], id_map: dict[str, str]) -> list[RelationDict]:
        mapped = []
        for rel in relations:
            sub_mapped = id_map.get(rel["subject"])
            obj_mapped = id_map.get(rel["object"])
            if sub_mapped and obj_mapped:
                mapped.append({"subject": sub_mapped, "predicate": rel["predicate"], "object": obj_mapped})
        return mapped