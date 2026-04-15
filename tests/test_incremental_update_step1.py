import logging
from pathlib import Path
from unittest.mock import patch

from app.parsers.exceptions import SourceParseError
from app.services.diff import collect_changed_files_from_diff
from app.services.incremental_update import _analyze_incremental_changes


def test_analyze_incremental_changes_builds_step1_result_for_mixed_diff(caplog) -> None:
    repo_path = Path(".").resolve()
    raw_diff = """
diff --git a/app/services/incremental_update.py b/app/services/incremental_update.py
--- a/app/services/incremental_update.py
+++ b/app/services/incremental_update.py
@@ -1,2 +1,3 @@
-from pathlib import Path
+from pathlib import Path
+from dataclasses import dataclass
diff --git a/app/services/diff.py b/app/services/diff.py
new file mode 100644
--- /dev/null
+++ b/app/services/diff.py
@@ -0,0 +1,2 @@
+from app.parsers.git_diff import parse_git_diff
+pass
diff --git a/legacy/deleted.py b/legacy/deleted.py
deleted file mode 100644
--- a/legacy/deleted.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def legacy():
-    return 1
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-# old
+# docs
diff --git a/app/api/router.py b/app/api/router.py
--- a/app/api/router.py
+++ b/app/api/router.py
@@ -1 +1 @@
-from fastapi import APIRouter
+from fastapi import APIRouter
""".strip()

    parsed_diff = collect_changed_files_from_diff(raw_diff)

    def fake_analyze_source_file(path: str | Path, *, include_relations: bool, fail_on_syntax_error: bool = True):
        if Path(path).name == "router.py":
            raise SourceParseError("synthetic parse error")

        from app.services.source_analysis import analyze_source_file as real_analyze_source_file

        return real_analyze_source_file(
            path,
            include_relations=include_relations,
            fail_on_syntax_error=fail_on_syntax_error,
        )

    caplog.set_level(logging.INFO)
    with patch("app.services.incremental_update.analyze_source_file", side_effect=fake_analyze_source_file):
        result = _analyze_incremental_changes(repo_path, parsed_diff)

    assert result.changed_files == [
        "app/services/incremental_update.py",
        "app/services/diff.py",
        "legacy/deleted.py",
        "README.md",
        "app/api/router.py",
    ]
    assert result.deleted_files == ["legacy/deleted.py"]

    analyzed_by_path = {item.path: item for item in result.analyzed_files}
    assert set(analyzed_by_path) == {
        "app/services/incremental_update.py",
        "app/services/diff.py",
    }
    assert analyzed_by_path["app/services/incremental_update.py"].language == "python"
    assert any(symbol.qualified_name == "run_incremental_update" for symbol in analyzed_by_path["app/services/incremental_update.py"].symbols)
    assert analyzed_by_path["app/services/diff.py"].language == "python"
    assert any(symbol.qualified_name == "collect_changed_files_from_diff" for symbol in analyzed_by_path["app/services/diff.py"].symbols)

    skipped = {(item.path, item.reason) for item in result.skipped_files}
    assert skipped == {
        ("README.md", "unsupported_language"),
        ("app/api/router.py", "parse_error"),
    }

    skip_records = [
        record
        for record in caplog.records
        if record.getMessage() == "incremental_update_file_skipped"
    ]
    assert {(record.path, record.reason) for record in skip_records} == skipped


def test_analyze_incremental_changes_marks_missing_file_as_skipped(caplog) -> None:
    raw_diff = """
diff --git a/app/missing.py b/app/missing.py
--- a/app/missing.py
+++ b/app/missing.py
@@ -1 +1 @@
-value = 1
+value = 2
""".strip()

    parsed_diff = collect_changed_files_from_diff(raw_diff)

    caplog.set_level(logging.INFO)
    result = _analyze_incremental_changes(Path(".").resolve(), parsed_diff)

    assert result.changed_files == ["app/missing.py"]
    assert result.analyzed_files == []
    assert result.deleted_files == []
    assert [(item.path, item.reason) for item in result.skipped_files] == [("app/missing.py", "missing_file")]

    skip_records = [
        record
        for record in caplog.records
        if record.getMessage() == "incremental_update_file_skipped"
    ]
    assert len(skip_records) == 1
    assert skip_records[0].path == "app/missing.py"
    assert skip_records[0].reason == "missing_file"
