from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from api.app.core.config import Settings
from api.app.repositories.interfaces import (
    AuthenticatedUser,
    CreateKnowledgeAssetPayload,
    KnowledgeRecord,
    KnowledgeRepository,
)
from api.app.schemas.knowledge import KnowledgeAssetResponse, KnowledgeVersionSummary
from api.app.services.storage import StorageService


from api.app.schemas.datasets import JobSummary


class KnowledgeService:
    def __init__(self, *, repository: KnowledgeRepository, storage_service: StorageService, settings: Settings):
        self._repository = repository
        self._storage_service = storage_service
        self._settings = settings

    async def create_knowledge_asset(
        self, current_user: AuthenticatedUser, upload_file: UploadFile
    ) -> tuple[KnowledgeAssetResponse, JobSummary]:
        workspace = await self._repository.ensure_workspace_for_user(current_user.user_id, current_user.email)
        original_filename = Path((upload_file.filename or "").strip()).name

        if not original_filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")

        extension = Path(original_filename).suffix.lower().lstrip(".")
        if extension not in self._settings.allowed_knowledge_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported knowledge file type '.{extension or 'unknown'}'.",
            )

        content = await upload_file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        if len(content) > self._settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds {self._settings.max_upload_size_mb} MB limit.",
            )

        asset_id = uuid4()
        version_id = uuid4()
        job_id = uuid4()
        storage_path = f"{workspace.id}/knowledge/{asset_id}/v1/{original_filename}"
        content_type = upload_file.content_type or _guess_knowledge_content_type(extension)

        stored_file = await self._storage_service.save(
            path=storage_path,
            content=content,
            content_type=content_type,
        )

        payload = CreateKnowledgeAssetPayload(
            workspace_id=workspace.id,
            knowledge_asset_id=asset_id,
            knowledge_version_id=version_id,
            job_id=job_id,
            created_by=current_user.user_id,
            title=Path(original_filename).stem,
            original_filename=original_filename,
            mime_type=content_type,
            storage_backend=stored_file.backend,
            storage_path=stored_file.path,
            file_size_bytes=len(content),
            checksum_sha256=sha256(content).hexdigest(),
        )

        try:
            record, job = await self._repository.create_knowledge_asset(payload)
        except Exception:
            await self._storage_service.delete(path=stored_file.path)
            raise

        return self._map_knowledge(record), JobSummary(
            id=job.id,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            error_message=job.error_message,
        )

    async def list_knowledge(self, current_user: AuthenticatedUser) -> list[KnowledgeAssetResponse]:
        workspace = await self._repository.ensure_workspace_for_user(current_user.user_id, current_user.email)
        assets = await self._repository.list_knowledge(workspace.id)
        return [self._map_knowledge(asset) for asset in assets]

    @staticmethod
    def _map_knowledge(record: KnowledgeRecord) -> KnowledgeAssetResponse:
        latest_version = None
        if record.latest_version:
            latest_version = KnowledgeVersionSummary(
                id=record.latest_version.id,
                version_number=record.latest_version.version_number,
                file_size_bytes=record.latest_version.file_size_bytes,
                created_at=record.latest_version.created_at,
            )
        return KnowledgeAssetResponse(
            id=record.id,
            workspace_id=record.workspace_id,
            title=record.title,
            original_filename=record.original_filename,
            mime_type=record.mime_type,
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
            latest_version=latest_version,
        )

    async def delete_knowledge_asset(self, current_user: AuthenticatedUser, asset_id: UUID) -> None:
        workspace = await self._repository.ensure_workspace_for_user(current_user.user_id, current_user.email)
        
        # Get info before deletion
        assets = await self._repository.list_knowledge(workspace.id)
        asset = next((a for a in assets if a.id == asset_id), None)
        
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge asset not found.")

        # 1. Cleanup Storage (V1)
        if asset.latest_version and asset.latest_version.storage_path:
            await self._storage_service.delete(path=asset.latest_version.storage_path)

        # 2. Delete from Repository (DB records - cascading will handle versions, jobs, chunks)
        await self._repository.delete_knowledge_asset(workspace.id, asset_id)


def _guess_knowledge_content_type(extension: str) -> str:
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/markdown",
    }.get(extension, "application/octet-stream")
