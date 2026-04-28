import os
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile, status

from api.app.core.config import Settings
from api.app.repositories.interfaces import AssetRepository, AuthenticatedUser
from api.app.schemas.assets import (
    AssetSummary, 
    AssetJobSummary, 
    AssetKind, 
    UploadAssetResponse,
    AssetDetail,
    AssetVersionSummary,
    AssetPreviewResponse,
    AssetProfileResponse
)
from api.app.services.datasets import DatasetService
from api.app.services.knowledge import KnowledgeService


class AssetService:
    def __init__(
        self,
        repository: AssetRepository,
        dataset_service: DatasetService,
        knowledge_service: KnowledgeService,
        settings: Settings,
    ):
        self._repository = repository
        self._dataset_service = dataset_service
        self._knowledge_service = knowledge_service
        self._settings = settings

    async def list_assets(self, current_user: AuthenticatedUser) -> list[AssetSummary]:
        workspace = await self._repository.ensure_workspace_for_user(
            current_user.user_id, current_user.email
        )
        records = await self._repository.list_assets(workspace.id)
        
        return [
            AssetSummary(
                id=r.id,
                kind=r.kind,
                title=r.title,
                original_filename=r.original_filename,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
                latest_job=AssetJobSummary(
                    id=r.latest_job.id,
                    status=r.latest_job.status,
                    error_message=r.latest_job.error_message
                ) if r.latest_job else None
            )
            for r in records
        ]

    async def upload_asset(self, current_user: AuthenticatedUser, file: UploadFile) -> UploadAssetResponse:
        extension = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
        
        if extension in self._settings.allowed_dataset_extensions:
            asset, job = await self._dataset_service.create_pending_dataset(current_user, file)
            kind = AssetKind.dataset
        elif extension in self._settings.allowed_knowledge_extensions:
            asset, job = await self._knowledge_service.create_knowledge_asset(current_user, file)
            kind = AssetKind.knowledge
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported asset file type '.{extension or 'unknown'}'.",
            )

        return UploadAssetResponse(
            asset_id=asset.id,
            kind=kind,
            job_id=job.id,
            status=job.status
        )

    async def delete_asset(self, current_user: AuthenticatedUser, asset_id: UUID) -> None:
        workspace = await self._repository.ensure_workspace_for_user(
            current_user.user_id, current_user.email
        )
        asset = await self._repository.get_asset(workspace.id, asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

        # Route through the lane-specific services so storage and materialized
        # artifacts are cleaned up before the DB rows are removed.
        if getattr(asset.kind, "value", asset.kind) == AssetKind.dataset.value:
            await self._dataset_service.delete_dataset(current_user, asset_id)
            return

        await self._knowledge_service.delete_knowledge_asset(current_user, asset_id)

    async def get_asset(self, current_user: AuthenticatedUser, asset_id: UUID) -> Optional[AssetDetail]:
        workspace = await self._repository.ensure_workspace_for_user(
            current_user.user_id, current_user.email
        )
        r = await self._repository.get_asset(workspace.id, asset_id)
        if not r:
            return None
            
        return AssetDetail(
            id=r.id,
            kind=r.kind,
            title=r.title,
            original_filename=r.original_filename,
            mime_type=r.mime_type,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            latest_version=AssetVersionSummary(
                id=r.latest_version.id,
                version_number=r.latest_version.version_number,
                storage_path=r.latest_version.storage_path,
                file_size_bytes=r.latest_version.file_size_bytes,
                created_at=r.latest_version.created_at
            ) if r.latest_version else None,
            latest_job=AssetJobSummary(
                id=r.latest_job.id,
                status=r.latest_job.status,
                error_message=r.latest_job.error_message
            ) if r.latest_job else None
        )

    async def get_asset_preview(self, current_user: AuthenticatedUser, asset_id: UUID) -> Optional[AssetPreviewResponse]:
        workspace = await self._repository.ensure_workspace_for_user(
            current_user.user_id, current_user.email
        )
        asset_stmt = await self._repository.get_asset(workspace.id, asset_id)
        if not asset_stmt: return None
        
        preview_data = await self._repository.get_asset_preview(workspace.id, asset_id)
        if preview_data is None: return None
        
        return AssetPreviewResponse(
            asset_id=asset_id,
            kind=asset_stmt.kind,
            preview_data=preview_data
        )

    async def get_asset_profile(self, current_user: AuthenticatedUser, asset_id: UUID) -> Optional[AssetProfileResponse]:
        workspace = await self._repository.ensure_workspace_for_user(
            current_user.user_id, current_user.email
        )
        asset_stmt = await self._repository.get_asset(workspace.id, asset_id)
        if not asset_stmt: return None
        
        profile_data = await self._repository.get_asset_profile(workspace.id, asset_id)
        if profile_data is None: return None
        
        return AssetProfileResponse(
            asset_id=asset_id,
            kind=asset_stmt.kind,
            profile_data=profile_data
        )
