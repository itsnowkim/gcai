from app.schemas.scan import CodebaseScanResult
from app.schemas.symbols import ExtractedSymbol, SymbolKind


CALLABLE_KINDS = {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CONSTRUCTOR}


def build_chroma_documents(scan_result: CodebaseScanResult) -> dict[str, list[dict[str, object]]]:
    documents_by_language: dict[str, list[dict[str, object]]] = {}

    for scanned_file in scan_result.scanned_files:
        for symbol in scanned_file.symbols:
            if symbol.kind not in CALLABLE_KINDS:
                continue
            if not symbol.body:
                continue
            documents_by_language.setdefault(scanned_file.language, []).append(_build_document_record(symbol))

    return documents_by_language


def _build_document_record(symbol: ExtractedSymbol) -> dict[str, object]:
    document_body = symbol.body.strip()
    document = f"{symbol.signature}\n{document_body}" if document_body else symbol.signature
    return {
        "id": symbol.id,
        "document": document,
        "metadata": {
            "symbol_id": symbol.id,
            "symbol_kind": symbol.kind,
            "language": symbol.language,
            "path": symbol.path,
            "name": symbol.name,
            "qualified_name": symbol.qualified_name,
            "parent_name": symbol.parent_name,
            "start_line": symbol.start_line,
            "end_line": symbol.end_line,
        },
    }
