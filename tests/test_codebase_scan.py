from pathlib import Path

import pytest

from app.services.codebase_scan import scan_codebase


def test_scan_codebase_collects_supported_files_and_relations(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.py").write_text(
        """
class Greeter:
    prefix = "hi"

    def greet(self, name):
        message = self.prefix
        return message
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "app" / "Service.java").write_text(
        """
package demo;
import demo.shared.BaseService;

class Service extends BaseService {
    String greet(String name) {
        return name;
    }
}
""".strip(),
        encoding="utf-8",
    )

    result = scan_codebase(tmp_path)

    assert result.scanned_file_count == 2
    scanned_by_path = {item.path: item for item in result.scanned_files}
    assert "app/service.py" in scanned_by_path
    assert "app/Service.java" in scanned_by_path
    assert any(symbol.qualified_name == "Greeter.greet" for symbol in scanned_by_path["app/service.py"].symbols)
    assert any(relation.destination == "demo.shared.BaseService" for relation in scanned_by_path["app/Service.java"].relations)


def test_scan_codebase_skips_unsupported_excluded_large_and_parse_error_files(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    (tmp_path / "large.py").write_text("x" * 64, encoding="utf-8")
    (tmp_path / "ok.py").write_text("value = 1\n", encoding="utf-8")

    result = scan_codebase(tmp_path, max_file_bytes=32)

    assert result.scanned_file_count == 1
    assert result.scanned_files[0].path == "ok.py"
    skipped = {(item.path, item.reason) for item in result.skipped_files}
    assert ("README.md", "unsupported_language") in skipped
    assert ("broken.py", "parse_error") in skipped
    assert ("large.py", "file_too_large") in skipped
    assert all(path != "node_modules/ignored.py" for path, _ in skipped)


@pytest.mark.parametrize("repo_factory", ["missing", "file"])
def test_scan_codebase_validates_repo_path(tmp_path: Path, repo_factory: str) -> None:
    if repo_factory == "missing":
        invalid_path = tmp_path / "missing"
    else:
        invalid_path = tmp_path / "repo.txt"
        invalid_path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError):
        scan_codebase(invalid_path)
