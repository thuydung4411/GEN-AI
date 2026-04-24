from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, status

from api.app.dependencies.auth import get_current_user
from api.app.dependencies.services import get_asset_service
from api.app.repositories.interfaces import AuthenticatedUser
from api.app.schemas.assets import (
    AssetListResponse, 
    UploadAssetResponse, 
    AssetSummary, 
    AssetDetail, 
    AssetPreviewResponse, 
    AssetProfileResponse
)
from api.app.services.assets import AssetService

router = APIRouter()


@router.get("", response_model=AssetListResponse)
async def list_assets(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> AssetListResponse:
    """
    List all assets (datasets and knowledge) in the current workspace.
    """
    items = await service.list_assets(current_user)
    return AssetListResponse(items=items)


@router.post("/upload", response_model=UploadAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> UploadAssetResponse:
    """
    Upload an asset (CSV, XLSX, PDF, DOCX, TXT, MD).
    The system automatically routes the file to the correct processing lane.
    """
    return await service.upload_asset(current_user, file)


@router.get("/{asset_id}", response_model=AssetDetail)
async def get_asset(
    asset_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> AssetDetail:
    """
    Get detailed information about a specific asset.
    """
    asset = await service.get_asset(current_user, asset_id)
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/preview", response_model=AssetPreviewResponse)
async def get_asset_preview(
    asset_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> AssetPreviewResponse:
    """
    Get a preview of the asset content (e.g., sheets for datasets, chunks for knowledge).
    """
    preview = await service.get_asset_preview(current_user, asset_id)
    if not preview:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset preview not available")
    return preview


@router.get("/{asset_id}/profile", response_model=AssetProfileResponse)
async def get_asset_profile(
    asset_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> AssetProfileResponse:
    """
    Get the data profile of the asset (only for datasets).
    """
    profile = await service.get_asset_profile(current_user, asset_id)
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset profile not available or not a dataset")
    return profile


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
):
    """
    Delete an asset and all its associated data.
    """
    await service.delete_asset(current_user, asset_id)
    return None
