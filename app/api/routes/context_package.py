from fastapi import APIRouter

from app.schemas.context_package import ContextPackageRequest, ContextPackageResult
from app.services.context_package import build_context_package

router = APIRouter()


@router.post("/analyze/context-package", response_model=ContextPackageResult)
async def analyze_context_package(payload: ContextPackageRequest) -> ContextPackageResult:
    return build_context_package(payload.repo_path, payload.diff)
