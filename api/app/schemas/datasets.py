from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DatasetVersionSummary(BaseModel):
    id: UUID
    version_number: int
    file_size_bytes: int
    created_at: datetime


class JobSummary(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class DatasetResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    original_filename: str
    mime_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: DatasetVersionSummary | None
    latest_job: JobSummary | None


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]


class UploadDatasetResponse(BaseModel):
    dataset: DatasetResponse
    job: JobSummary


class DatasetSheetSummary(BaseModel):
    id: UUID
    name: str
    row_count: int | None
    column_count: int | None
    created_at: datetime


class ColumnProfileSummary(BaseModel):
    id: UUID
    sheet_name: str | None
    column_name: str
    data_type: str
    null_count: int | None
    distinct_count: int | None
    min_value: str | None
    max_value: str | None
    sample_values: dict | None


class DatasetPreviewResponse(BaseModel):
    sheet_name: str | None
    columns: list[str]
    rows: list[dict] # JSON rows


class DatasetProfileResponse(BaseModel):
    sheets: list[DatasetSheetSummary]
    columns: list[ColumnProfileSummary]
