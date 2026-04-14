from enum import StrEnum

from pydantic import BaseModel, Field


class SymbolKind(StrEnum):
    FILE = "file"
    IMPORT = "import"
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
    TYPE_ALIAS = "type_alias"


class ExtractedSymbol(BaseModel):
    id: str
    kind: SymbolKind
    language: str
    path: str
    name: str
    qualified_name: str
    signature: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    code: str
    body: str | None = None
    parent_name: str | None = None
    parameters: list[str] = Field(default_factory=list)
    super_types: list[str] = Field(default_factory=list)
    aliased_type: str | None = None
    is_static: bool = False


class SymbolExtractionResult(BaseModel):
    path: str
    language: str
    symbols: list[ExtractedSymbol]
