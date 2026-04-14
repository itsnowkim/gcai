from enum import StrEnum

from pydantic import BaseModel, Field


class RelationKind(StrEnum):
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    READS = "reads"
    WRITES = "writes"


class ExtractedRelation(BaseModel):
    id: str
    kind: RelationKind
    path: str
    source: str
    destination: str
    metadata: dict[str, str | bool] = Field(default_factory=dict)


class RelationExtractionResult(BaseModel):
    path: str
    language: str
    relations: list[ExtractedRelation]
