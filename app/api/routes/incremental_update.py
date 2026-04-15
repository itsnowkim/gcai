from fastapi import APIRouter

from app.schemas.incremental_update import IncrementalUpdateRequest, IncrementalUpdateResult
from app.services.incremental_update import run_incremental_update

router = APIRouter()


@router.post("/graph/incremental-update", response_model=IncrementalUpdateResult)
async def incremental_update(payload: IncrementalUpdateRequest) -> IncrementalUpdateResult:
    return run_incremental_update(payload.repo_path, payload.diff)
