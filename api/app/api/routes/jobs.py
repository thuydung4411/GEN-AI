from uuid import UUID

from fastapi import APIRouter, Depends

from api.app.dependencies.auth import get_current_user
from api.app.dependencies.services import get_dataset_service
from api.app.repositories.interfaces import AuthenticatedUser
from api.app.schemas.jobs import JobResponse
from api.app.services.datasets import DatasetService

router = APIRouter()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
) -> JobResponse:
    return await service.get_job(current_user, job_id)
