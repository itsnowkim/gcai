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


class GraphPath(BaseModel):
    seed_id: str
    terminal_node_id: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    hop_count: int


class GraphExploreResult(BaseModel):
    seeds: list[SeedNode] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    max_depth: int = 1
    allowed_relation_kinds: list[RelationKind] = Field(default_factory=list)


class OneHopGraphResult(GraphExploreResult):
    pass
