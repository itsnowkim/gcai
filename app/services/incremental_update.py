from pathlib import Path

from app.core.exceptions import GCAIError
from app.services.diff import collect_changed_files_from_diff


def run_incremental_update(repo_path: str, raw_diff: str):
    _validate_repo_path(repo_path)
    collect_changed_files_from_diff(raw_diff)
    raise GCAIError(
        "Incremental graph update service is not implemented yet. Complete phase 3 first.",
        error_code="incremental_update_not_implemented",
        status_code=501,
    )


def _validate_repo_path(repo_path: str) -> None:
    path = Path(repo_path).resolve()
    if not path.exists():
        raise GCAIError(f"Repository path does not exist: {path}", error_code="invalid_repo_path", status_code=400)
    if not path.is_dir():
        raise GCAIError(f"Repository path is not a directory: {path}", error_code="invalid_repo_path", status_code=400)
