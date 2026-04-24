from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.app.models.entities import (
    AssetKind,
    Dataset,
    DatasetStatus,
    DatasetVersion,
    DatasetSheet,
    ColumnProfile,
    IngestionJob,
    JobStatus,
    KnowledgeAsset,
    KnowledgeVersion,
    KnowledgeChunk,
    Workspace,
    WorkspaceMember,
    Asset,
    AssetVersion,
)
from api.app.repositories.interfaces import (
    AssetRepository,
    CreateDatasetBundlePayload,
    CreateKnowledgeAssetPayload,
    DatasetRecord,
    DatasetRepository,
    DatasetVersionRecord,
    JobRecord,
    KnowledgeRecord,
    KnowledgeRepository,
    KnowledgeVersionRecord,
    WorkspaceRecord,
    DatasetSheetRecord,
    ColumnProfileRecord,
    KnowledgeChunkRecord,
    AssetDetailRecord,
    AssetVersionRecord,
    AssetSummaryRecord,
)


class SqlAlchemyKnowledgeRepository(KnowledgeRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def ensure_workspace_for_user(self, user_id: UUID, email: str | None) -> WorkspaceRecord:
        statement = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        existing_workspace = await self._session.scalar(statement)

        if existing_workspace is not None:
            return WorkspaceRecord(
                id=existing_workspace.id,
                slug=existing_workspace.slug,
                name=existing_workspace.name,
            )

        slug = f"workspace-{str(user_id)[:8]}"
        name = f"{(email or 'User').split('@')[0]}'s Workspace"

        workspace = Workspace(id=uuid4(), slug=slug, name=name)
        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user_id,
            email=email,
            role="owner",
        )

        self._session.add(workspace)
        self._session.add(member)
        await self._session.commit()

        return WorkspaceRecord(id=workspace.id, slug=workspace.slug, name=workspace.name)

    async def create_knowledge_asset(
        self, payload: CreateKnowledgeAssetPayload
    ) -> tuple[KnowledgeRecord, JobRecord]:
        asset = KnowledgeAsset(
            id=payload.knowledge_asset_id,
            workspace_id=payload.workspace_id,
            title=payload.title,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            status=DatasetStatus.pending,
        )
        # Unified Asset record
        gen_asset = Asset(
            id=payload.knowledge_asset_id,
            workspace_id=payload.workspace_id,
            kind=AssetKind.knowledge,
            title=payload.title,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            status=DatasetStatus.pending,
        )
        version = KnowledgeVersion(
            id=payload.knowledge_version_id,
            knowledge_asset_id=payload.knowledge_asset_id,
            version_number=1,
            storage_backend=payload.storage_backend,
            storage_path=payload.storage_path,
            file_size_bytes=payload.file_size_bytes,
            checksum_sha256=payload.checksum_sha256,
        )
        # Unified AssetVersion record
        gen_version = AssetVersion(
            id=payload.knowledge_version_id,
            asset_id=payload.knowledge_asset_id,
            version_number=1,
            storage_backend=payload.storage_backend,
            storage_path=payload.storage_path,
            file_size_bytes=payload.file_size_bytes,
            checksum_sha256=payload.checksum_sha256,
        )
        job = IngestionJob(
            id=payload.job_id,
            workspace_id=payload.workspace_id,
            asset_id=payload.knowledge_asset_id,
            asset_version_id=payload.knowledge_version_id,
            asset_kind=AssetKind.knowledge,
            knowledge_asset_id=payload.knowledge_asset_id,
            knowledge_version_id=payload.knowledge_version_id,
            status=JobStatus.pending,
            created_by=payload.created_by,
        )

        self._session.add(asset)
        self._session.add(gen_asset)
        self._session.add(version)
        self._session.add(gen_version)
        await self._session.flush() # Ensure parent entities have IDs and are in DB state
        
        self._session.add(job)
        await self._session.commit()
        
        # Explicitly refresh the attributes needed for _to_knowledge_record mapping
        await self._session.refresh(asset, ["versions", "jobs"])
        await self._session.refresh(job)

        return (
            self._to_knowledge_record(asset),
            JobRecord(
                id=job.id,
                status=job.status.value,
                created_at=job.created_at,
                updated_at=job.updated_at,
                error_message=job.error_message,
            )
        )

    async def save_knowledge_chunks(
        self, 
        chunks: list[KnowledgeChunkRecord]
    ) -> None:
        entities = [
            KnowledgeChunk(
                id=c.id,
                knowledge_version_id=c.knowledge_version_id,
                asset_version_id=c.asset_version_id or c.knowledge_version_id,
                content=c.content,
                embedding=c.embedding,
                metadata_json=c.metadata_json,
                chunk_index=c.chunk_index,
            ) for c in chunks
        ]
        self._session.add_all(entities)
        await self._session.commit()

    async def list_knowledge(self, workspace_id: UUID) -> list[KnowledgeRecord]:
        statement = (
            select(KnowledgeAsset)
            .where(KnowledgeAsset.workspace_id == workspace_id)
            .options(selectinload(KnowledgeAsset.versions), selectinload(KnowledgeAsset.jobs))
            .order_by(KnowledgeAsset.created_at.desc())
        )
        assets = (await self._session.scalars(statement)).all()
        return [self._to_knowledge_record(asset) for asset in assets]

    async def delete_knowledge_asset(self, workspace_id: UUID, knowledge_id: UUID) -> None:
        statement = delete(KnowledgeAsset).where(
            KnowledgeAsset.workspace_id == workspace_id,
            KnowledgeAsset.id == knowledge_id
        )
        await self._session.execute(statement)
        await self._session.execute(
            delete(Asset).where(
                Asset.workspace_id == workspace_id,
                Asset.id == knowledge_id,
            )
        )
        await self._session.commit()

    @staticmethod
    def _to_knowledge_record(asset: KnowledgeAsset) -> KnowledgeRecord:
        latest_version = max(asset.versions, key=lambda v: v.version_number, default=None)
        latest_job = max(asset.jobs, key=lambda j: j.created_at, default=None)
        
        version_record = None
        if latest_version:
            version_record = KnowledgeVersionRecord(
                id=latest_version.id,
                version_number=latest_version.version_number,
                storage_path=latest_version.storage_path,
                file_size_bytes=latest_version.file_size_bytes,
                created_at=latest_version.created_at,
            )
            
        job_record = None
        if latest_job:
            job_record = JobRecord(
                id=latest_job.id,
                status=latest_job.status.value,
                created_at=latest_job.created_at,
                updated_at=latest_job.updated_at,
                error_message=latest_job.error_message,
            )
            
        return KnowledgeRecord(
            id=asset.id,
            workspace_id=asset.workspace_id,
            title=asset.title,
            original_filename=asset.original_filename,
            mime_type=asset.mime_type,
            status=asset.status.value,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            latest_version=version_record,
            latest_job=job_record,
        )


class SqlAlchemyDatasetRepository(DatasetRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def ensure_workspace_for_user(self, user_id: UUID, email: str | None) -> WorkspaceRecord:
        statement = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        existing_workspace = await self._session.scalar(statement)

        if existing_workspace is not None:
            return WorkspaceRecord(
                id=existing_workspace.id,
                slug=existing_workspace.slug,
                name=existing_workspace.name,
            )

        slug = f"workspace-{str(user_id)[:8]}"
        name = f"{(email or 'User').split('@')[0]}'s Workspace"

        workspace = Workspace(id=uuid4(), slug=slug, name=name)
        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user_id,
            email=email,
            role="owner",
        )

        self._session.add(workspace)
        self._session.add(member)
        await self._session.commit()

        return WorkspaceRecord(id=workspace.id, slug=workspace.slug, name=workspace.name)

    async def create_dataset_bundle(
        self, payload: CreateDatasetBundlePayload
    ) -> tuple[DatasetRecord, JobRecord]:
        dataset = Dataset(
            id=payload.dataset_id,
            workspace_id=payload.workspace_id,
            created_by=payload.created_by,
            title=payload.title,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            status=DatasetStatus.pending,
        )
        # Unified Asset record
        gen_asset = Asset(
            id=payload.dataset_id,
            workspace_id=payload.workspace_id,
            kind=AssetKind.dataset,
            title=payload.title,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            status=DatasetStatus.pending,
        )
        version = DatasetVersion(
            id=payload.dataset_version_id,
            dataset_id=payload.dataset_id,
            workspace_id=payload.workspace_id,
            version_number=1,
            storage_backend=payload.storage_backend,
            storage_path=payload.storage_path,
            file_size_bytes=payload.file_size_bytes,
            checksum_sha256=payload.checksum_sha256,
            uploaded_by=payload.created_by,
        )
        # Unified AssetVersion record
        gen_version = AssetVersion(
            id=payload.dataset_version_id,
            asset_id=payload.dataset_id,
            version_number=1,
            storage_backend=payload.storage_backend,
            storage_path=payload.storage_path,
            file_size_bytes=payload.file_size_bytes,
            checksum_sha256=payload.checksum_sha256,
        )
        job = IngestionJob(
            id=payload.job_id,
            workspace_id=payload.workspace_id,
            asset_id=payload.dataset_id,
            asset_version_id=payload.dataset_version_id,
            asset_kind=AssetKind.dataset,
            dataset_id=payload.dataset_id,
            dataset_version_id=payload.dataset_version_id,
            status=JobStatus.pending,
            created_by=payload.created_by,
        )

        self._session.add(dataset)
        self._session.add(gen_asset)
        self._session.add(version)
        self._session.add(gen_version)
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(dataset)
        await self._session.refresh(version)
        await self._session.refresh(job)

        return (
            DatasetRecord(
                id=dataset.id,
                workspace_id=dataset.workspace_id,
                title=dataset.title,
                original_filename=dataset.original_filename,
                mime_type=dataset.mime_type,
                status=dataset.status.value,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                latest_version=DatasetVersionRecord(
                    id=version.id,
                    version_number=version.version_number,
                    storage_path=version.storage_path,
                    file_size_bytes=version.file_size_bytes,
                    created_at=version.created_at,
                ),
                latest_job=JobRecord(
                    id=job.id,
                    status=job.status.value,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    error_message=job.error_message,
                ),
            ),
            JobRecord(
                id=job.id,
                status=job.status.value,
                created_at=job.created_at,
                updated_at=job.updated_at,
                error_message=job.error_message,
            ),
        )

    async def save_dataset_metadata(
        self, 
        sheets: list[DatasetSheetRecord], 
        profiles: list[ColumnProfileRecord]
    ) -> None:
        sheet_entities = [
            DatasetSheet(
                id=s.id,
                dataset_id=s.dataset_id,
                dataset_version_id=s.dataset_version_id,
                asset_version_id=s.asset_version_id or s.dataset_version_id,
                name=s.name,
                row_count=s.row_count,
                column_count=s.column_count,
            ) for s in sheets
        ]
        profile_entities = [
            ColumnProfile(
                id=p.id,
                dataset_id=p.dataset_id,
                dataset_version_id=p.dataset_version_id,
                asset_version_id=p.asset_version_id or p.dataset_version_id,
                sheet_name=p.sheet_name,
                column_name=p.column_name,
                data_type=p.data_type,
                null_count=p.null_count,
                distinct_count=p.distinct_count,
                min_value=p.min_value,
                max_value=p.max_value,
                sample_values=p.sample_values,
            ) for p in profiles
        ]
        self._session.add_all(sheet_entities)
        self._session.add_all(profile_entities)
        await self._session.commit()

    async def delete_dataset(self, workspace_id: UUID, dataset_id: UUID) -> None:
        statement = delete(Dataset).where(
            Dataset.workspace_id == workspace_id,
            Dataset.id == dataset_id
        )
        await self._session.execute(statement)
        await self._session.execute(
            delete(Asset).where(
                Asset.workspace_id == workspace_id,
                Asset.id == dataset_id,
            )
        )
        await self._session.commit()

    async def list_datasets(self, workspace_id: UUID) -> list[DatasetRecord]:
        statement = (
            select(Dataset)
            .where(Dataset.workspace_id == workspace_id, Dataset.deleted_at.is_(None))
            .options(selectinload(Dataset.versions), selectinload(Dataset.jobs))
            .order_by(Dataset.created_at.desc())
        )
        datasets = (await self._session.scalars(statement)).all()
        return [self._to_dataset_record(dataset) for dataset in datasets]

    async def get_job(self, workspace_id: UUID, job_id: UUID) -> JobRecord | None:
        statement = select(IngestionJob).where(
            IngestionJob.workspace_id == workspace_id,
            IngestionJob.id == job_id,
        )
        job = await self._session.scalar(statement)
        if job is None:
            return None

        return JobRecord(
            id=job.id,
            status=job.status.value,
            created_at=job.created_at,
            updated_at=job.updated_at,
            error_message=job.error_message,
        )

    async def get_dataset_sheets(self, dataset_version_id: UUID) -> list[DatasetSheetRecord]:
        statement = select(DatasetSheet).where(DatasetSheet.dataset_version_id == dataset_version_id)
        result = await self._session.scalars(statement)
        return [
            DatasetSheetRecord(
                id=s.id, dataset_id=s.dataset_id, dataset_version_id=s.dataset_version_id,
                name=s.name, row_count=s.row_count, column_count=s.column_count, created_at=s.created_at,
                asset_version_id=s.asset_version_id,
            ) for s in result.all()
        ]

    async def get_column_profiles(self, dataset_version_id: UUID) -> list[ColumnProfileRecord]:
        statement = select(ColumnProfile).where(ColumnProfile.dataset_version_id == dataset_version_id)
        result = await self._session.scalars(statement)
        return [
            ColumnProfileRecord(
                id=p.id, dataset_id=p.dataset_id, dataset_version_id=p.dataset_version_id,
                sheet_name=p.sheet_name, column_name=p.column_name, data_type=p.data_type,
                null_count=p.null_count, distinct_count=p.distinct_count, min_value=p.min_value,
                max_value=p.max_value, sample_values=p.sample_values, created_at=p.created_at,
                asset_version_id=p.asset_version_id,
            ) for p in result.all()
        ]

    @staticmethod
    def _to_dataset_record(dataset: Dataset) -> DatasetRecord:
        latest_version = max(dataset.versions, key=lambda version: version.version_number, default=None)
        latest_job = max(dataset.jobs, key=lambda job: job.created_at, default=None)

        version_record = None
        if latest_version is not None:
            version_record = DatasetVersionRecord(
                id=latest_version.id,
                version_number=latest_version.version_number,
                storage_path=latest_version.storage_path,
                file_size_bytes=latest_version.file_size_bytes,
                created_at=latest_version.created_at,
            )

        job_record = None
        if latest_job is not None:
            job_record = JobRecord(
                id=latest_job.id,
                status=latest_job.status.value,
                created_at=latest_job.created_at,
                updated_at=latest_job.updated_at,
                error_message=latest_job.error_message,
            )

        return DatasetRecord(
            id=dataset.id,
            workspace_id=dataset.workspace_id,
            title=dataset.title,
            original_filename=dataset.original_filename,
            mime_type=dataset.mime_type,
            status=dataset.status.value,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
            latest_version=version_record,
            latest_job=job_record,
        )


class SqlAlchemyAssetRepository(AssetRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def ensure_workspace_for_user(self, user_id: UUID, email: str | None) -> WorkspaceRecord:
        # Re-using the logic from other repositories but centralizing it here for AssetService
        statement = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        existing_workspace = await self._session.scalar(statement)

        if existing_workspace is not None:
            return WorkspaceRecord(
                id=existing_workspace.id,
                slug=existing_workspace.slug,
                name=existing_workspace.name,
            )

        slug = f"workspace-{str(user_id)[:8]}"
        name = f"{(email or 'User').split('@')[0]}'s Workspace"

        workspace = Workspace(id=uuid4(), slug=slug, name=name)
        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user_id,
            email=email,
            role="owner",
        )

        self._session.add(workspace)
        self._session.add(member)
        await self._session.commit()

        return WorkspaceRecord(id=workspace.id, slug=workspace.slug, name=workspace.name)

    async def list_assets(self, workspace_id: UUID) -> list[AssetSummaryRecord]:
        # Now using the consolidated Asset model
        statement = (
            select(Asset)
            .where(Asset.workspace_id == workspace_id)
            .options(selectinload(Asset.jobs))
            .order_by(Asset.created_at.desc())
        )
        assets = (await self._session.scalars(statement)).all()
        
        return [
            AssetSummaryRecord(
                id=a.id,
                kind=a.kind,
                title=a.title,
                original_filename=a.original_filename,
                status=a.status.value,
                created_at=a.created_at,
                updated_at=a.updated_at,
                latest_job=self._get_job_record(a.jobs)
            )
            for a in assets
        ]

    async def get_asset(self, workspace_id: UUID, asset_id: UUID) -> AssetDetailRecord | None:
        statement = (
            select(Asset)
            .where(Asset.workspace_id == workspace_id, Asset.id == asset_id)
            .options(selectinload(Asset.versions), selectinload(Asset.jobs))
        )
        asset = await self._session.scalar(statement)
        if not asset:
            return None
            
        latest_version = max(asset.versions, key=lambda v: v.version_number, default=None)
        
        return AssetDetailRecord(
            id=asset.id,
            kind=asset.kind,
            title=asset.title,
            original_filename=asset.original_filename,
            mime_type=asset.mime_type,
            status=asset.status.value,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            latest_version=AssetVersionRecord(
                id=latest_version.id,
                version_number=latest_version.version_number,
                storage_path=latest_version.storage_path,
                file_size_bytes=latest_version.file_size_bytes,
                created_at=latest_version.created_at
            ) if latest_version else None,
            latest_job=self._get_job_record(asset.jobs)
        )

    async def delete_asset(self, workspace_id: UUID, asset_id: UUID) -> None:
        # Delete from the unified Asset table (cascades to Dataset/KnowledgeAsset if referenced)
        # Note: In Phase 2a we still have legacy tables. Migration 005 uses FKs.
        # Cascade deletion works because of REFERENCES assets(id) ON DELETE CASCADE in legacy tables 
        # (Wait, I didn't add those to legacy tables, I added them to assets referring to legacy? No.)
        # Actually, legacy tables should refer to assets.
        
        # For now, let's keep the two-step delete for safety until we drop legacy tables.
        stmt1 = delete(Dataset).where(Dataset.workspace_id == workspace_id, Dataset.id == asset_id)
        await self._session.execute(stmt1)
        
        stmt2 = delete(KnowledgeAsset).where(KnowledgeAsset.workspace_id == workspace_id, KnowledgeAsset.id == asset_id)
        await self._session.execute(stmt2)
        
        # Delete from unified table
        stmt3 = delete(Asset).where(Asset.workspace_id == workspace_id, Asset.id == asset_id)
        await self._session.execute(stmt3)
        
        await self._session.commit()

    async def get_asset_preview(self, workspace_id: UUID, asset_id: UUID) -> list[dict] | None:
        # Route preview based on kind. 
        # Check kind first
        asset_stmt = select(Asset).where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
        asset = await self._session.scalar(asset_stmt)
        if not asset: return None
        
        if asset.kind == AssetKind.dataset:
            # Re-use DatasetRepository logic by querying Dataset sheets/profiles
            # (In Phase 2, we might move this to a generic ParserService)
            # For now, let's just query DatasetSheet
            # We need the version_id
            version_stmt = select(AssetVersion).where(AssetVersion.asset_id == asset_id).order_by(AssetVersion.version_number.desc()).limit(1)
            version = await self._session.scalar(version_stmt)
            if not version: return None
            
            # Simple list of sheets as "preview"
            sheets_stmt = select(DatasetSheet).where(DatasetSheet.asset_version_id == version.id)
            sheets = (await self._session.scalars(sheets_stmt)).all()
            return [{"sheet_name": s.name, "row_count": s.row_count} for s in sheets]
        
        elif asset.kind == AssetKind.knowledge:
            # Preview chunks
            version_stmt = select(AssetVersion).where(AssetVersion.asset_id == asset_id).order_by(AssetVersion.version_number.desc()).limit(1)
            version = await self._session.scalar(version_stmt)
            if not version: return None
            
            chunks_stmt = select(KnowledgeChunk).where(KnowledgeChunk.asset_version_id == version.id).limit(10)
            chunks = (await self._session.scalars(chunks_stmt)).all()
            return [{"content": c.content[:200] + "..."} for c in chunks]
            
        return None

    async def get_asset_profile(self, workspace_id: UUID, asset_id: UUID) -> dict | None:
        # Only relevant for datasets
        asset_stmt = select(Asset).where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
        asset = await self._session.scalar(asset_stmt)
        if not asset or asset.kind != AssetKind.dataset: return None
        
        version_stmt = select(AssetVersion).where(AssetVersion.asset_id == asset_id).order_by(AssetVersion.version_number.desc()).limit(1)
        version = await self._session.scalar(version_stmt)
        if not version: return None
        
        profiles_stmt = select(ColumnProfile).where(ColumnProfile.asset_version_id == version.id)
        profiles = (await self._session.scalars(profiles_stmt)).all()
        return {
            "columns": [
                {
                    "name": p.column_name,
                    "type": p.data_type,
                    "distinct_count": p.distinct_count,
                    "null_count": p.null_count
                } for p in profiles
            ]
        }

    @staticmethod
    def _get_job_record(jobs: list[IngestionJob]) -> JobRecord | None:
        latest = max(jobs, key=lambda j: j.created_at, default=None)
        if not latest:
            return None
        return JobRecord(
            id=latest.id,
            status=latest.status.value,
            created_at=latest.created_at,
            updated_at=latest.updated_at,
            error_message=latest.error_message
        )
