from app.core.exceptions import GCAIError


def run_incremental_update(repo_path: str, raw_diff: str):
    del repo_path, raw_diff
    raise GCAIError(
        "Incremental graph update service is not implemented yet. Complete phase 3 first.",
        error_code="incremental_update_not_implemented",
        status_code=501,
    )
