from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.parsers.exceptions import ParserConfigurationError, SourceFileReadError, SourceParseError, UnsupportedLanguageError
from app.schemas.changed_code import ChangedCodeContextResult, ChangedSymbolSeed
from app.schemas.context_package import ContextPackageResult, ModifiedCodeSnippet, NeighborCodeSnippet
from app.schemas.graph import GraphExploreResult, GraphNode
from app.services.changed_code import collect_changed_code_context
from app.services.diff import collect_changed_files_from_diff
from app.services.graph_explore import explore_two_hop_from_changed_code
from app.services.source_analysis import analyze_source_file
from app.storage.chroma import ChromaCodeReader, create_chroma_client, verify_chroma_connectivity

logger = get_logger(__name__)

GRAPH_NEIGHBOR_LIMIT = 10
VECTOR_NEIGHBOR_LIMIT = 5


def build_modified_code(changed_code_context: ChangedCodeContextResult) -> list[ModifiedCodeSnippet]:
    snippets: dict[str, ModifiedCodeSnippet] = {}

    for changed_file in changed_code_context.changed_files:
        if not changed_file.source_loaded or changed_file.skip_reason is not None:
            continue

        for seed in changed_file.symbols:
            code = seed.symbol.code.strip()
            if not code:
                continue

            snippets[seed.symbol.id] = ModifiedCodeSnippet(
                symbol_id=seed.symbol.id,
                path=seed.symbol.path,
                language=seed.symbol.language,
                kind=seed.symbol.kind.value,
                qualified_name=seed.symbol.qualified_name,
                start_line=seed.symbol.start_line,
                end_line=seed.symbol.end_line,
                code=code,
                matched_line_ranges=list(seed.matched_line_ranges),
            )

    result = _sort_modified_code(snippets.values())
    logger.info("modified_code_built", extra={"repo_path": changed_code_context.repo_path, "count": len(result)})
    return result


def build_neighbor_code(
    repo_path: str | Path,
    changed_code_context: ChangedCodeContextResult,
    graph_result: GraphExploreResult,
) -> list[NeighborCodeSnippet]:
    changed_symbol_ids = {item.symbol.id for item in changed_code_context.changed_symbols}
    snippets: dict[tuple[str, str, int, int], NeighborCodeSnippet] = {}

    for snippet in _build_graph_neighbor_code(repo_path, graph_result, changed_symbol_ids):
        snippets.setdefault(_neighbor_dedupe_key(snippet), snippet)

    for snippet in _build_vector_neighbor_code(changed_code_context, changed_symbol_ids):
        snippets.setdefault(_neighbor_dedupe_key(snippet), snippet)

    return _sort_neighbor_code(snippets.values())


def build_context_package(repo_path: str | Path, raw_diff: str) -> ContextPackageResult:
    diff_result = collect_changed_files_from_diff(raw_diff)
    changed_code_context = collect_changed_code_context(repo_path, diff_result)
    graph_result = explore_two_hop_from_changed_code(changed_code_context)
    modified_code = build_modified_code(changed_code_context)
    neighbor_code = build_neighbor_code(repo_path, changed_code_context, graph_result)

    result = ContextPackageResult(
        repo_path=changed_code_context.repo_path,
        changed_files=changed_code_context.changed_files,
        changed_symbols=changed_code_context.changed_symbols,
        graph_paths=graph_result.graph_paths,
        modified_code=modified_code,
        neighbor_code=neighbor_code,
    )
    logger.info(
        "context_package_built",
        extra={
            "repo_path": result.repo_path,
            "changed_files": len(result.changed_files),
            "changed_symbols": len(result.changed_symbols),
            "graph_paths": len(result.graph_paths),
            "modified_code": len(result.modified_code),
            "neighbor_code": len(result.neighbor_code),
        },
    )
    return result


def _sort_modified_code(items: Iterable[ModifiedCodeSnippet]) -> list[ModifiedCodeSnippet]:
    return sorted(items, key=lambda item: (item.path, item.start_line, item.end_line, item.qualified_name, item.symbol_id))


def _build_graph_neighbor_code(
    repo_path: str | Path,
    graph_result: GraphExploreResult,
    changed_symbol_ids: set[str],
) -> list[NeighborCodeSnippet]:
    repo_root = Path(repo_path).resolve()
    path_to_symbols = _load_symbols_from_graph_paths(repo_root, graph_result)
    snippets: list[NeighborCodeSnippet] = []

    for node in graph_result.nodes:
        if len(snippets) >= GRAPH_NEIGHBOR_LIMIT:
            break
        if node.id in changed_symbol_ids:
            continue

        symbol = _match_graph_node_symbol(node, path_to_symbols.get(node.path, []))
        if symbol is None:
            continue

        code = symbol.code.strip()
        if not code:
            continue

        snippets.append(
            NeighborCodeSnippet(
                symbol_id=symbol.id,
                path=symbol.path,
                language=symbol.language,
                kind=symbol.kind.value,
                qualified_name=symbol.qualified_name,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                code=code,
                source="graph",
            )
        )

    return snippets


def _load_symbols_from_graph_paths(repo_root: Path, graph_result: GraphExploreResult) -> dict[str, list[object]]:
    symbols_by_path: dict[str, list[object]] = {}
    for node in graph_result.nodes:
        path_key = node.path
        if path_key in symbols_by_path:
            continue

        source_path = repo_root / path_key
        if not source_path.exists():
            symbols_by_path[path_key] = []
            continue

        try:
            analysis = analyze_source_file(source_path, include_relations=False, fail_on_syntax_error=False)
        except (UnsupportedLanguageError, SourceFileReadError, SourceParseError, ParserConfigurationError):
            symbols_by_path[path_key] = []
            continue

        symbols_by_path[path_key] = list(analysis.symbol_result.symbols)

    return symbols_by_path


def _match_graph_node_symbol(node: GraphNode, symbols: list[object]):
    for symbol in symbols:
        if symbol.id == node.id:
            return symbol

    for symbol in symbols:
        if (
            symbol.qualified_name == node.qualified_name
            and symbol.start_line == node.start_line
            and symbol.end_line == node.end_line
        ):
            return symbol

    for symbol in symbols:
        if symbol.qualified_name == node.qualified_name:
            return symbol

    return None


def _build_vector_neighbor_code(
    changed_code_context: ChangedCodeContextResult,
    changed_symbol_ids: set[str],
) -> list[NeighborCodeSnippet]:
    query_seeds = [seed for seed in changed_code_context.changed_symbols if seed.symbol.language and seed.symbol.code.strip()]
    if not query_seeds:
        return []

    settings = get_settings()
    client = create_chroma_client(settings)
    try:
        verify_chroma_connectivity(client)
        reader = ChromaCodeReader(client, collection_prefix=settings.chroma_collection_prefix)
        snippets: dict[str, NeighborCodeSnippet] = {}

        for seed in query_seeds:
            if len(snippets) >= VECTOR_NEIGHBOR_LIMIT:
                break

            query_text = (seed.symbol.body or seed.symbol.code).strip()
            rows = reader.query_similar_code(
                language=seed.symbol.language,
                query_text=query_text,
                top_k=VECTOR_NEIGHBOR_LIMIT,
            )
            for row in rows:
                metadata = row["metadata"]
                symbol_id = str(metadata.get("symbol_id") or row["id"] or "")
                if not symbol_id or symbol_id in changed_symbol_ids or symbol_id in snippets:
                    continue

                language = str(metadata.get("language") or "")
                if language != seed.symbol.language:
                    continue

                document = str(row.get("document") or "").strip()
                if not document:
                    continue

                snippets[symbol_id] = NeighborCodeSnippet(
                    symbol_id=symbol_id,
                    path=str(metadata.get("path") or ""),
                    language=language,
                    kind=str(metadata.get("symbol_kind") or ""),
                    qualified_name=str(metadata.get("qualified_name") or metadata.get("name") or symbol_id),
                    start_line=int(metadata.get("start_line") or 0),
                    end_line=int(metadata.get("end_line") or 0),
                    code=document,
                    source="vector",
                )
                if len(snippets) >= VECTOR_NEIGHBOR_LIMIT:
                    break

        return list(snippets.values())
    finally:
        close_client = getattr(client, "close", None)
        if callable(close_client):
            close_client()


def _sort_neighbor_code(items: Iterable[NeighborCodeSnippet]) -> list[NeighborCodeSnippet]:
    source_rank = {"graph": 0, "vector": 1}
    return sorted(
        items,
        key=lambda item: (
            source_rank[item.source],
            item.path,
            item.start_line,
            item.end_line,
            item.qualified_name,
            item.symbol_id,
        ),
    )


def _neighbor_dedupe_key(item: NeighborCodeSnippet) -> tuple[str, str]:
    return (item.qualified_name, _normalize_code(item.code))


def _normalize_code(value: str) -> str:
    return "\n".join(line.strip() for line in value.strip().splitlines())
