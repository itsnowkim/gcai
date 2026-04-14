from pydantic import BaseModel, Field

from app.schemas.diff import ChangeType, DiffLineRange
from app.schemas.symbols import ExtractedSymbol


class ChangedSymbolSeed(BaseModel):
    symbol: ExtractedSymbol
    matched_line_ranges: list[DiffLineRange] = Field(default_factory=list)


class ChangedFileContext(BaseModel):
    path: str
    change_type: ChangeType
    old_path: str | None = None
    new_path: str | None = None
    language: str | None = None
    source_path: str | None = None
    source_code: str | None = None
    changed_line_ranges: list[DiffLineRange] = Field(default_factory=list)
    symbols: list[ChangedSymbolSeed] = Field(default_factory=list)
    source_loaded: bool = False
    skip_reason: str | None = None


class ChangedCodeContextResult(BaseModel):
    repo_path: str
    changed_files: list[ChangedFileContext] = Field(default_factory=list)
    changed_symbols: list[ChangedSymbolSeed] = Field(default_factory=list)
