from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.changed_code import ChangedFileContext, ChangedSymbolSeed
from app.schemas.diff import DiffLineRange
from app.schemas.graph import GraphPath


class ModifiedCodeSnippet(BaseModel):
    symbol_id: str
    path: str
    language: str
    kind: str
    qualified_name: str
    start_line: int
    end_line: int
    code: str
    matched_line_ranges: list[DiffLineRange] = Field(default_factory=list)


class NeighborCodeSnippet(BaseModel):
    symbol_id: str
    path: str
    language: str
    kind: str
    qualified_name: str
    start_line: int
    end_line: int
    code: str
    source: Literal["graph", "vector"]


class ContextPackageResult(BaseModel):
    repo_path: str
    changed_files: list[ChangedFileContext] = Field(default_factory=list)
    changed_symbols: list[ChangedSymbolSeed] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    modified_code: list[ModifiedCodeSnippet] = Field(default_factory=list)
    neighbor_code: list[NeighborCodeSnippet] = Field(default_factory=list)


class ContextPackageRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    diff: str = Field(min_length=1)
