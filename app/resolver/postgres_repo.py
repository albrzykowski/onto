import logging

import asyncpg

from app.config import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from app.resolver.models import EntityType

logger = logging.getLogger(__name__)


class PostgresRepo:
    def __init__(
        self,
        host: str = POSTGRES_HOST,
        port: int = POSTGRES_PORT,
        user: str = POSTGRES_USER,
        password: str = POSTGRES_PASSWORD,
        database: str = POSTGRES_DB,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._pool: asyncpg.Pool | None = None

    async def connect(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                min_size=2,
                max_size=10,
            )
            logger.info("Connected to PostgreSQL")

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def init_schema(self):
        await self.connect()
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    canonical_id UUID NOT NULL,
                    label TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    embedding_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    subject_id UUID NOT NULL,
                    predicate TEXT NOT NULL,
                    object_id UUID NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS merge_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    canonical_entity_id UUID NOT NULL,
                    merged_entity_id UUID NOT NULL,
                    merged_at TIMESTAMP DEFAULT NOW()
                )
            """)
            logger.info("Database schema initialized")

    async def insert_entity(self, canonical_id: str, label: str, entity_type: EntityType, embedding_id: str | None = None) -> str:
        async with self._pool.acquire() as conn:
            entity_id = await conn.fetchval(
                """
                INSERT INTO entities (canonical_id, label, entity_type, embedding_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                canonical_id,
                label,
                entity_type.value,
                embedding_id,
            )
            return str(entity_id)

    async def update_canonical_id(self, entity_id: str, canonical_id: str):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE entities SET canonical_id = $1, updated_at = NOW() WHERE id = $2",
                canonical_id,
                entity_id,
            )

    async def record_merge(self, canonical_entity_id: str, merged_entity_id: str):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO merge_history (canonical_entity_id, merged_entity_id) VALUES ($1, $2)",
                canonical_entity_id,
                merged_entity_id,
            )

    async def insert_relation(self, subject_id: str, predicate: str, object_id: str) -> str:
        async with self._pool.acquire() as conn:
            relation_id = await conn.fetchval(
                """
                INSERT INTO relations (subject_id, predicate, object_id)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                subject_id,
                predicate,
                object_id,
            )
            return str(relation_id)

    async def get_canonical_entity_by_id(self, entity_id: str) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, canonical_id, label, entity_type FROM entities WHERE id = $1",
                entity_id,
            )
            if row:
                return {
                    "id": str(row["id"]),
                    "canonical_id": str(row["canonical_id"]),
                    "label": row["label"],
                    "entity_type": row["entity_type"],
                }
            return None