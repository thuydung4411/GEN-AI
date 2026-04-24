from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile

from api.app.dependencies.auth import get_current_user
from api.app.dependencies.services import get_dataset_service
from api.app.repositories.interfaces import AuthenticatedUser
from api.app.schemas.datasets import (
    DatasetListResponse, 
    UploadDatasetResponse,
    DatasetPreviewResponse,
    DatasetProfileResponse
)
from api.app.services.datasets import DatasetService

router = APIRouter()


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetListResponse:
    items = await service.list_datasets(current_user)
    return DatasetListResponse(items=items)


@router.post("/upload", response_model=UploadDatasetResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
) -> UploadDatasetResponse:
    dataset, job = await service.create_pending_dataset(current_user, file)
    return UploadDatasetResponse(dataset=dataset, job=job)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def get_dataset_preview(
    dataset_id: UUID,
    sheet_name: str | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetPreviewResponse:
    return await service.get_preview(current_user, dataset_id, sheet_name)


@router.get("/{dataset_id}/profile", response_model=DatasetProfileResponse)
async def get_dataset_profile(
    dataset_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetProfileResponse:
    return await service.get_profile(current_user, dataset_id)


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
):
    await service.delete_dataset(current_user, dataset_id)
    return None
