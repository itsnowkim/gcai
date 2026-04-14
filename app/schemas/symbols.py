from enum import StrEnum

from pydantic import BaseModel


class SymbolKind(StrEnum):
    FILE = "file"
    NAMESPACE = "namespace"
    CLASS = "class"
    STRUCT = "struct"
    INTERFACE = "interface"
    ENUM = "enum"
    ENUM_MEMBER = "enum_member"
    UNION = "union"
    RECORD = "record"
    ANNOTATION = "annotation"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    VARIABLE = "variable"


class ExtractedSymbol(BaseModel):
    id: str
    kind: SymbolKind
    language: str
    path: str
    name: str
    qualified_name: str
    signature: str
    start_line: int
    end_line: int
    code: str
    body: str | None = None
    parent_name: str | None = None


class SymbolExtractionResult(BaseModel):
    path: str
    language: str
    symbols: list[ExtractedSymbol]
