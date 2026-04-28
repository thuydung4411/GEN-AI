from pathlib import Path
from uuid import uuid4

import pytest

from api.app.models.entities import AssetKind
from api.app.repositories.in_memory import (
    InMemoryAssetRepository,
    InMemoryDatasetRepository,
    InMemoryKnowledgeRepository,
)
from api.app.repositories.interfaces import (
    CreateDatasetBundlePayload,
    CreateKnowledgeAssetPayload,
)


def make_dataset_payload(workspace_id, created_by):
    dataset_id = uuid4()
    version_id = uuid4()
    return CreateDatasetBundlePayload(
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        dataset_version_id=version_id,
        job_id=uuid4(),
        created_by=created_by,
        title="Sales",
        original_filename="sales.csv",
        mime_type="text/csv",
        storage_backend="local",
        storage_path=f"{workspace_id}/{dataset_id}/v1/sales.csv",
        file_size_bytes=12,
        checksum_sha256="dataset-checksum",
    )


def make_knowledge_payload(workspace_id, created_by):
    asset_id = uuid4()
    version_id = uuid4()
    return CreateKnowledgeAssetPayload(
        workspace_id=workspace_id,
        knowledge_asset_id=asset_id,
        knowledge_version_id=version_id,
        job_id=uuid4(),
        created_by=created_by,
        title="Policy",
        original_filename="policy.pdf",
        mime_type="application/pdf",
        storage_backend="local",
        storage_path=f"{workspace_id}/knowledge/{asset_id}/v1/policy.pdf",
        file_size_bytes=34,
        checksum_sha256="knowledge-checksum",
    )


@pytest.mark.asyncio
async def test_generic_asset_repository_merges_dataset_and_knowledge_lanes():
    workspaces_by_user = {}
    dataset_repo = InMemoryDatasetRepository(workspaces_by_user)
    knowledge_repo = InMemoryKnowledgeRepository(workspaces_by_user)
    asset_repo = InMemoryAssetRepository(dataset_repo, knowledge_repo)

    user_id = uuid4()
    workspace = await asset_repo.ensure_workspace_for_user(user_id, "owner@example.com")

    dataset_payload = make_dataset_payload(workspace.id, user_id)
    knowledge_payload = make_knowledge_payload(workspace.id, user_id)
    await dataset_repo.create_dataset_bundle(dataset_payload)
    await knowledge_repo.create_knowledge_asset(knowledge_payload)

    assets = await asset_repo.list_assets(workspace.id)

    assert {asset.kind for asset in assets} == {AssetKind.dataset, AssetKind.knowledge}
    assert {asset.id for asset in assets} == {
        dataset_payload.dataset_id,
        knowledge_payload.knowledge_asset_id,
    }

    dataset_detail = await asset_repo.get_asset(workspace.id, dataset_payload.dataset_id)
    knowledge_detail = await asset_repo.get_asset(
        workspace.id,
        knowledge_payload.knowledge_asset_id,
    )

    assert dataset_detail is not None
    assert dataset_detail.kind == AssetKind.dataset
    assert dataset_detail.latest_version.id == dataset_payload.dataset_version_id
    assert dataset_detail.latest_job.id == dataset_payload.job_id
    assert knowledge_detail is not None
    assert knowledge_detail.kind == AssetKind.knowledge
    assert knowledge_detail.latest_version.id == knowledge_payload.knowledge_version_id
    assert knowledge_detail.latest_job.id == knowledge_payload.job_id


@pytest.mark.asyncio
async def test_generic_asset_delete_is_workspace_scoped():
    workspaces_by_user = {}
    dataset_repo = InMemoryDatasetRepository(workspaces_by_user)
    knowledge_repo = InMemoryKnowledgeRepository(workspaces_by_user)
    asset_repo = InMemoryAssetRepository(dataset_repo, knowledge_repo)

    owner_id = uuid4()
    owner_workspace = await asset_repo.ensure_workspace_for_user(owner_id, "owner@example.com")
    payload = make_dataset_payload(owner_workspace.id, owner_id)
    await dataset_repo.create_dataset_bundle(payload)

    other_workspace = await asset_repo.ensure_workspace_for_user(uuid4(), "other@example.com")
    await asset_repo.delete_asset(other_workspace.id, payload.dataset_id)

    assert await asset_repo.get_asset(owner_workspace.id, payload.dataset_id) is not None
    assert await asset_repo.get_asset(other_workspace.id, payload.dataset_id) is None


def test_unified_asset_migration_backfills_legacy_rows_and_jobs():
    migration_path = Path(__file__).resolve().parents[2] / "infra/sql/005_unified_assets.sql"
    if not migration_path.exists():
        pytest.skip("infra/sql is not mounted in this runtime")

    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS assets" in migration
    assert "CREATE TABLE IF NOT EXISTS asset_versions" in migration
    assert "FROM datasets" in migration
    assert "FROM knowledge_assets" in migration
    assert "ADD COLUMN IF NOT EXISTS asset_id" in migration
    assert "ADD COLUMN IF NOT EXISTS asset_version_id" in migration
    assert "ADD COLUMN IF NOT EXISTS asset_kind" in migration
    assert "UPDATE ingestion_jobs SET asset_id = dataset_id" in migration
    assert "UPDATE ingestion_jobs SET asset_id = knowledge_asset_id" in migration
