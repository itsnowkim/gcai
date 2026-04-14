from pydantic import BaseModel, Field

from app.schemas.relations import RelationKind


class SeedNode(BaseModel):
    id: str
    path: str
    kind: str
    qualified_name: str


class GraphNode(BaseModel):
    id: str
    kind: str
    language: str
    path: str
    name: str
    qualified_name: str
    signature: str
    start_line: int
    end_line: int


class GraphEdge(BaseModel):
    id: str
    kind: RelationKind
    source_id: str
    destination_id: str
    path: str
    source: str
    destination: str


class OneHopGraphResult(BaseModel):
    seeds: list[SeedNode] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
