from datetime import datetime
from enum import Enum
from uuid import UUID
from typing import Literal, Union, Optional

from pydantic import BaseModel, Field


class AssetKind(str, Enum):
    dataset = "dataset"
    knowledge = "knowledge"


class AssetJobSummary(BaseModel):
    id: UUID
    status: str
    error_message: Optional[str] = None


class AssetSummary(BaseModel):
    id: UUID
    kind: AssetKind
    title: str
    original_filename: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_job: Optional[AssetJobSummary] = None


class AssetListResponse(BaseModel):
    items: list[AssetSummary]


class UploadAssetResponse(BaseModel):
    asset_id: UUID
    kind: AssetKind
    job_id: UUID
    status: str = "pending"


class AssetVersionSummary(BaseModel):
    id: UUID
    version_number: int
    storage_path: str
    file_size_bytes: int
    created_at: datetime


class AssetDetail(BaseModel):
    id: UUID
    kind: AssetKind
    title: str
    original_filename: str
    mime_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[AssetVersionSummary] = None
    latest_job: Optional[AssetJobSummary] = None


class AssetPreviewResponse(BaseModel):
    asset_id: UUID
    kind: AssetKind
    preview_data: list[dict]


class AssetProfileResponse(BaseModel):
    asset_id: UUID
    kind: AssetKind
    profile_data: dict
