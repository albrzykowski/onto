from dataclasses import dataclass
from enum import Enum
from typing import TypedDict


class EntityType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    EVENT = "Event"
    CONCEPT = "Concept"
    PRODUCT = "Product"
    OTHER = "Other"


class ResolutionAction(str, Enum):
    MERGE = "merge"
    CREATE_NEW = "create_new"


class EntityDict(TypedDict):
    id: str
    label: str
    type: str


class RelationDict(TypedDict):
    subject: str
    predicate: str
    object: str


@dataclass
class Entity:
    id: str
    label: str
    type: EntityType


@dataclass
class Relation:
    subject: str
    predicate: str
    object: str


@dataclass
class ResolutionDecision:
    action: ResolutionAction
    canonical_entity_id: str
    confidence: float
    merged_with: list[str]


@dataclass
class ResolverInput:
    entities: list[EntityDict]
    relations: list[RelationDict]


@dataclass
class ResolverOutput:
    decisions: list[ResolutionDecision]
    relations: list[RelationDict]