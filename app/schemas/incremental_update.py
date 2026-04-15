from pydantic import BaseModel, Field


class IncrementalUpdateRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    diff: str = Field(min_length=1)


class IncrementalUpdateResult(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    updated_nodes: int = 0
    updated_edges: int = 0
    reindexed_embeddings: int = 0
    status: str
