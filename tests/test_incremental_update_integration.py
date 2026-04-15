import os
import shutil
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

from app.core.settings import get_settings
from app.services import run_incremental_update, run_initial_index
from app.storage.chroma.client import create_chroma_client
from app.storage.chroma.collections import build_callable_collection_name
from app.storage.neo4j.client import create_neo4j_driver


def test_incremental_update_with_real_storages() -> None:
    repo_path = _make_repo_dir("incremental")
    previous_env, previous_download_path = _configure_local_embedding_cache()
    try:
        with patch.object(ONNXMiniLM_L6_V2, "__call__", new=_fake_embed):
            (repo_path / "app").mkdir()
            target_file = repo_path / "app" / "service.py"
            target_file.write_text(
                """
def helper(value):
    return value.strip()


class Greeter:
    def greet(self, name):
        return helper(name)
""".strip(),
                encoding="utf-8",
            )

            _clear_neo4j_database()
            _clear_chroma_collections()

            initial_result = run_initial_index(repo_path)
            assert initial_result.upserted_nodes > 0
            assert initial_result.upserted_edges > 0
            assert initial_result.upserted_documents == 2

            target_file.write_text(
                """
def helper(value):
    return value.strip().upper()


def format_name(name):
    return helper(name)


class Greeter:
    def greet(self, name):
        return format_name(name)
""".strip(),
                encoding="utf-8",
            )

            raw_diff = """
diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -1,7 +1,11 @@
 def helper(value):
-    return value.strip()
+    return value.strip().upper()
 
 
+def format_name(name):
+    return helper(name)
+
+
 class Greeter:
     def greet(self, name):
-        return helper(name)
+        return format_name(name)
""".strip()

            result = run_incremental_update(str(repo_path), raw_diff)

            assert result.changed_files == ["app/service.py"]
            assert result.updated_nodes > 0
            assert result.updated_edges > 0
            assert result.reindexed_embeddings == 3
            assert result.status == "ok"

            storage_path = target_file.resolve().as_posix()
            qualified_names = _get_neo4j_symbol_names_for_path(storage_path)
            assert "helper" in qualified_names
            assert "format_name" in qualified_names
            assert "Greeter.greet" in qualified_names

            call_destinations = _get_neo4j_call_destinations(storage_path, "Greeter.greet")
            assert "format_name" in call_destinations
            assert "helper" not in call_destinations

            chroma_names = _get_chroma_document_names("python", storage_path)
            assert chroma_names == ["Greeter.greet", "format_name", "helper"]
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)
        _clear_neo4j_database()
        _clear_chroma_collections()
        _restore_environment(previous_env, previous_download_path)


def _get_neo4j_symbol_names_for_path(path: str) -> list[str]:
    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                """
MATCH (symbol:Symbol)
WHERE symbol.path = $path
RETURN symbol.qualified_name AS qualified_name
ORDER BY qualified_name
""".strip(),
                path=path,
            )
            return [record["qualified_name"] for record in result]
    finally:
        driver.close()


def _get_neo4j_call_destinations(path: str, source_qualified_name: str) -> list[str]:
    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                """
MATCH (source:Symbol)-[relation:RELATES_TO]->(destination:Symbol)
WHERE source.path = $path
  AND source.qualified_name = $source_qualified_name
  AND relation.kind = 'calls'
RETURN destination.qualified_name AS qualified_name
ORDER BY qualified_name
""".strip(),
                path=path,
                source_qualified_name=source_qualified_name,
            )
            return [record["qualified_name"] for record in result]
    finally:
        driver.close()


def _get_chroma_document_names(language: str, path: str) -> list[str]:
    settings = get_settings()
    client = create_chroma_client(settings)
    try:
        collection = client.get_or_create_collection(
            name=build_callable_collection_name(
                collection_prefix=settings.chroma_collection_prefix,
                language=language,
            )
        )
        result = collection.get(
            where={"path": path},
            include=["metadatas"],
        )
        metadatas = result.get("metadatas", [])
        names = [
            metadata["qualified_name"]
            for metadata in metadatas
            if isinstance(metadata, dict) and isinstance(metadata.get("qualified_name"), str)
        ]
        return sorted(names)
    finally:
        close_client = getattr(client, "close", None)
        if callable(close_client):
            close_client()


def _clear_neo4j_database() -> None:
    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
    finally:
        driver.close()


def _clear_chroma_collections() -> None:
    settings = get_settings()
    client = create_chroma_client(settings)
    try:
        prefix = f"{settings.chroma_collection_prefix.lower()}-"
        for collection in client.list_collections():
            name = collection.name if hasattr(collection, "name") else str(collection)
            if not name.startswith(prefix):
                continue
            client.delete_collection(name=name)
    finally:
        close_client = getattr(client, "close", None)
        if callable(close_client):
            close_client()


def _make_repo_dir(label: str) -> Path:
    path = Path(".tmp_graph_tests") / f"{label}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _fake_embed(self, input):
    return [[float(index + 1)] * 8 for index, _ in enumerate(input)]


def _configure_local_embedding_cache() -> tuple[dict[str, str | None], str]:
    cache_dir = Path(".cache")
    home_dir = Path(".home")
    cache_dir.mkdir(exist_ok=True)
    home_dir.mkdir(exist_ok=True)

    previous_env = {
        "HOME": os.environ.get("HOME"),
        "USERPROFILE": os.environ.get("USERPROFILE"),
        "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME"),
    }
    resolved_cache = str(cache_dir.resolve())
    resolved_home = str(home_dir.resolve())
    previous_download_path = ONNXMiniLM_L6_V2.DOWNLOAD_PATH
    os.environ["HOME"] = resolved_home
    os.environ["USERPROFILE"] = resolved_home
    os.environ["XDG_CACHE_HOME"] = resolved_cache
    ONNXMiniLM_L6_V2.DOWNLOAD_PATH = str(
        (cache_dir / "chroma" / "onnx_models" / "all-MiniLM-L6-v2").resolve()
    )
    return previous_env, previous_download_path


def _restore_environment(previous_env: dict[str, str | None], previous_download_path: str) -> None:
    for key, value in previous_env.items():
        if value is None:
            os.environ.pop(key, None)
            continue
        os.environ[key] = value
    ONNXMiniLM_L6_V2.DOWNLOAD_PATH = previous_download_path
