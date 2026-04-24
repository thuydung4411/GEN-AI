from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KnowledgeVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    file_size_bytes: int
    created_at: datetime


class KnowledgeAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    title: str
    original_filename: str
    mime_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: KnowledgeVersionSummary | None = None
