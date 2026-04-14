from pydantic import BaseModel, Field

from app.schemas.relations import ExtractedRelation
from app.schemas.symbols import ExtractedSymbol


class SkippedFile(BaseModel):
    path: str
    reason: str


class ScannedFile(BaseModel):
    path: str
    language: str
    symbols: list[ExtractedSymbol]
    relations: list[ExtractedRelation]


class CodebaseScanResult(BaseModel):
    repo_path: str
    scanned_files: list[ScannedFile] = Field(default_factory=list)
    skipped_files: list[SkippedFile] = Field(default_factory=list)

    @property
    def scanned_file_count(self) -> int:
        return len(self.scanned_files)

    @property
    def skipped_file_count(self) -> int:
        return len(self.skipped_files)
