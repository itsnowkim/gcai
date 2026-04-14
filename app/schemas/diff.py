from enum import StrEnum

from pydantic import BaseModel, Field


class ChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


class DiffLineRange(BaseModel):
    start_line: int
    line_count: int


class DiffHunk(BaseModel):
    old_start_line: int
    old_line_count: int
    new_start_line: int
    new_line_count: int


class ParsedDiffFile(BaseModel):
    path: str
    change_type: ChangeType
    old_path: str | None = None
    new_path: str | None = None
    changed_line_ranges: list[DiffLineRange] = Field(default_factory=list)
    hunks: list[DiffHunk] = Field(default_factory=list)


class ParsedDiffResult(BaseModel):
    files: list[ParsedDiffFile] = Field(default_factory=list)
