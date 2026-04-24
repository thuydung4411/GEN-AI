from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from api.app.repositories.interfaces import (
    ColumnProfileRecord,
    CreateDatasetBundlePayload,
    CreateKnowledgeAssetPayload,
    DatasetRecord,
    DatasetRepository,
    DatasetSheetRecord,
    DatasetVersionRecord,
    JobRecord,
    KnowledgeChunkRecord,
    KnowledgeRecord,
    KnowledgeRepository,
    KnowledgeVersionRecord,
    WorkspaceRecord,
)


class InMemoryKnowledgeRepository(KnowledgeRepository):
    def __init__(self):
        self._workspaces_by_user: dict[UUID, WorkspaceRecord] = {}
        self._knowledge_by_workspace: dict[UUID, list[KnowledgeRecord]] = {}
        self._chunks_by_version: dict[UUID, list[KnowledgeChunkRecord]] = {}

    async def ensure_workspace_for_user(self, user_id: UUID, email: str | None) -> WorkspaceRecord:
        workspace = self._workspaces_by_user.get(user_id)
        if workspace is not None:
            return workspace

        name = f"{(email or 'User').split('@')[0]}'s Workspace"
        workspace = WorkspaceRecord(id=uuid4(), slug=f"workspace-{str(user_id)[:8]}", name=name)
        self._workspaces_by_user[user_id] = workspace
        self._knowledge_by_workspace[workspace.id] = []
        return workspace

    async def create_knowledge_asset(
        self, payload: CreateKnowledgeAssetPayload
    ) -> tuple[KnowledgeRecord, JobRecord]:
        now = datetime.now(tz=timezone.utc)
        version = KnowledgeVersionRecord(
            id=payload.knowledge_version_id,
            version_number=1,
            storage_path=payload.storage_path,
            file_size_bytes=payload.file_size_bytes,
            created_at=now,
        )
        job = JobRecord(
            id=payload.job_id,
            status="pending",
            created_at=now,
            updated_at=now,
            error_message=None,
        )
        asset = KnowledgeRecord(
            id=payload.knowledge_asset_id,
            workspace_id=payload.workspace_id,
            title=payload.title,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            status="pending",
            created_at=now,
            updated_at=now,
            latest_version=version,
            latest_job=job,
        )
        self._knowledge_by_workspace.setdefault(payload.workspace_id, []).append(asset)
        return asset, job

    async def list_knowledge(self, workspace_id: UUID) -> list[KnowledgeRecord]:
        return [replace(asset) for asset in self._knowledge_by_workspace.get(workspace_id, [])]

    async def save_knowledge_chunks(self, chunks: list[KnowledgeChunkRecord]) -> None:
        if not chunks:
            return
        version_id = chunks[0].knowledge_version_id
        self._chunks_by_version[version_id] = [replace(chunk) for chunk in chunks]

    async def delete_knowledge_asset(self, workspace_id: UUID, knowledge_id: UUID) -> None:
        assets = self._knowledge_by_workspace.get(workspace_id, [])
        self._knowledge_by_workspace[workspace_id] = [asset for asset in assets if asset.id != knowledge_id]


class InMemoryDatasetRepository(DatasetRepository):
    def __init__(self):
        self._workspaces_by_user: dict[UUID, WorkspaceRecord] = {}
        self._datasets_by_workspace: dict[UUID, list[DatasetRecord]] = {}
        self._jobs_by_workspace: dict[UUID, dict[UUID, JobRecord]] = {}
        self._sheets_by_version: dict[UUID, list[DatasetSheetRecord]] = {}
        self._profiles_by_version: dict[UUID, list[ColumnProfileRecord]] = {}

    async def ensure_workspace_for_user(self, user_id: UUID, email: str | None) -> WorkspaceRecord:
        workspace = self._workspaces_by_user.get(user_id)
        if workspace is not None:
            return workspace

        name = f"{(email or 'User').split('@')[0]}'s Workspace"
        workspace = WorkspaceRecord(id=uuid4(), slug=f"workspace-{str(user_id)[:8]}", name=name)
        self._workspaces_by_user[user_id] = workspace
        self._datasets_by_workspace[workspace.id] = []
        self._jobs_by_workspace[workspace.id] = {}
        return workspace

    async def create_dataset_bundle(
        self, payload: CreateDatasetBundlePayload
    ) -> tuple[DatasetRecord, JobRecord]:
        now = datetime.now(tz=timezone.utc)
        version = DatasetVersionRecord(
            id=payload.dataset_version_id,
            version_number=1,
            storage_path=payload.storage_path,
            file_size_bytes=payload.file_size_bytes,
            created_at=now,
        )
        job = JobRecord(
            id=payload.job_id,
            status="pending",
            created_at=now,
            updated_at=now,
            error_message=None,
        )
        dataset = DatasetRecord(
            id=payload.dataset_id,
            workspace_id=payload.workspace_id,
            title=payload.title,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            status="pending",
            created_at=now,
            updated_at=now,
            latest_version=version,
            latest_job=job,
        )
        self._datasets_by_workspace.setdefault(payload.workspace_id, []).append(dataset)
        self._jobs_by_workspace.setdefault(payload.workspace_id, {})[payload.job_id] = job
        return dataset, job

    async def list_datasets(self, workspace_id: UUID) -> list[DatasetRecord]:
        return [replace(dataset) for dataset in self._datasets_by_workspace.get(workspace_id, [])]

    async def get_job(self, workspace_id: UUID, job_id: UUID) -> JobRecord | None:
        job = self._jobs_by_workspace.get(workspace_id, {}).get(job_id)
        return replace(job) if job is not None else None

    async def save_dataset_metadata(
        self,
        sheets: list[DatasetSheetRecord],
        profiles: list[ColumnProfileRecord],
    ) -> None:
        if sheets:
            version_id = sheets[0].dataset_version_id
            self._sheets_by_version[version_id] = [replace(sheet) for sheet in sheets]
        if profiles:
            version_id = profiles[0].dataset_version_id
            self._profiles_by_version[version_id] = [replace(profile) for profile in profiles]

    async def get_dataset_sheets(self, dataset_version_id: UUID) -> list[DatasetSheetRecord]:
        return [replace(sheet) for sheet in self._sheets_by_version.get(dataset_version_id, [])]

    async def get_column_profiles(self, dataset_version_id: UUID) -> list[ColumnProfileRecord]:
        return [replace(profile) for profile in self._profiles_by_version.get(dataset_version_id, [])]

    async def delete_dataset(self, workspace_id: UUID, dataset_id: UUID) -> None:
        datasets = self._datasets_by_workspace.get(workspace_id, [])
        self._datasets_by_workspace[workspace_id] = [dataset for dataset in datasets if dataset.id != dataset_id]
