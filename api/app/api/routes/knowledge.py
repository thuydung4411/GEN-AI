from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, status

from api.app.dependencies.auth import get_current_user
from api.app.dependencies.services import get_knowledge_service
from api.app.repositories.interfaces import AuthenticatedUser
from api.app.schemas.knowledge import KnowledgeAssetResponse
from api.app.services.knowledge import KnowledgeService

router = APIRouter()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_knowledge(
    file: UploadFile,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """
    Upload a knowledge asset (PDF, DOCX, TXT, MD).
    These will be processed for RAG (Search) purposes.
    """
    asset, _job = await service.create_knowledge_asset(user, file)
    return asset


@router.get("", response_model=list[KnowledgeAssetResponse])
async def list_knowledge(
    user: AuthenticatedUser = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """
    List all knowledge assets in the current workspace.
    """
    return await service.list_knowledge(user)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_asset(
    asset_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """
    Delete a knowledge asset and all its associated data.
    """
    await service.delete_knowledge_asset(user, asset_id)
    return None
