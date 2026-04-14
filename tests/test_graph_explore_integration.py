import shutil
from pathlib import Path
from uuid import uuid4

from app.parsers.git_diff import parse_git_diff
from app.services.changed_code import collect_changed_code_context
from app.services.codebase_scan import scan_codebase
from app.services.graph_explore import build_seed_nodes, explore_graph_neighbors
from app.services.graph_ingest import ingest_scan_result_to_neo4j
from app.storage.neo4j.client import create_neo4j_driver
from app.core.settings import get_settings
from app.schemas.relations import RelationKind


def test_two_hop_exploration_with_real_neo4j() -> None:
    repo_path = _make_repo_dir("graph")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
def normalize(value):
    return value.strip()


def helper(value):
    return normalize(value)


class Greeter:
    def greet(self, name):
        return helper(name)
""".strip(),
            encoding="utf-8",
        )

        _clear_neo4j_database()

        scan_result = scan_codebase(repo_path)
        ingest_scan_result_to_neo4j(scan_result)

        diff_result = parse_git_diff(
            """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -9,3 +9,3 @@ class Greeter:
 class Greeter:
     def greet(self, name):
         return helper(name)
"""
        )
        changed_code_context = collect_changed_code_context(repo_path, diff_result)
        graph_result = explore_graph_neighbors(
            build_seed_nodes(changed_code_context),
            max_depth=2,
            allowed_relation_kinds=(RelationKind.CALLS,),
        )

        node_names = {node.qualified_name for node in graph_result.nodes}
        edge_ids = {edge.id for edge in graph_result.edges}
        path_signatures = {tuple(path.node_ids) for path in graph_result.graph_paths}
        node_ids_by_name = {node.qualified_name: node.id for node in graph_result.nodes}

        assert "Greeter.greet" in node_names
        assert "helper" in node_names
        assert "normalize" in node_names
        assert any("Greeter.greet->helper" in edge_id for edge_id in edge_ids)
        assert any("helper->normalize" in edge_id for edge_id in edge_ids)
        assert (
            node_ids_by_name["Greeter.greet"],
            node_ids_by_name["helper"],
            node_ids_by_name["normalize"],
        ) in path_signatures
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def _clear_neo4j_database() -> None:
    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
    finally:
        driver.close()


def _make_repo_dir(label: str) -> Path:
    path = Path(".tmp_graph_tests") / f"{label}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path
