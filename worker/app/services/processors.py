import os
from uuid import uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.app.models.entities import (
    ColumnProfile,
    DatasetSheet,
    DatasetVersion,
    KnowledgeChunk,
    KnowledgeVersion,
)
from api.app.services.parsers.knowledge import KnowledgeParser
from api.app.services.parsers.tabular import TabularParser
from worker.app.services.storage import StorageReader


class StructuredLaneProcessor:
    def __init__(self, settings, storage_reader: StorageReader, parser: TabularParser):
        self._settings = settings
        self._storage_reader = storage_reader
        self._parser = parser

    async def process(self, session: AsyncSession, job: dict) -> None:
        asset_id = job["asset_id"]
        version = await session.scalar(
            select(DatasetVersion).where(DatasetVersion.id == job["asset_version_id"])
        )
        if not version:
            raise ValueError(f"DatasetVersion {job['asset_version_id']} not found")

        await self.mark_processing(session, asset_id)
        temp_path = await _write_temp_file(self._settings, self._storage_reader, version.storage_path)
        try:
            sheets, profiles = self._parser.parse_and_materialize(
                temp_path,
                job["workspace_id"],
                asset_id,
                job["asset_version_id"],
            )
            if not sheets:
                raise ValueError("Dataset asset produced no sheets to materialize")

            await session.execute(
                delete(DatasetSheet).where(DatasetSheet.dataset_version_id == job["asset_version_id"])
            )
            await session.execute(
                delete(ColumnProfile).where(ColumnProfile.dataset_version_id == job["asset_version_id"])
            )
            session.add_all([*sheets, *profiles])
        finally:
            _remove_file(temp_path)

        await self.mark_ready(session, asset_id)

    async def mark_processing(self, session: AsyncSession, asset_id) -> None:
        await session.execute(
            text("UPDATE datasets SET status = 'processing', updated_at = NOW() WHERE id = :id"),
            {"id": asset_id},
        )

    async def mark_ready(self, session: AsyncSession, asset_id) -> None:
        await session.execute(
            text("UPDATE datasets SET status = 'ready', updated_at = NOW() WHERE id = :id"),
            {"id": asset_id},
        )

    async def mark_failed(self, session: AsyncSession, asset_id) -> None:
        await session.execute(
            text("UPDATE datasets SET status = 'failed', updated_at = NOW() WHERE id = :id"),
            {"id": asset_id},
        )


class KnowledgeLaneProcessor:
    def __init__(self, settings, storage_reader: StorageReader, parser: KnowledgeParser):
        self._settings = settings
        self._storage_reader = storage_reader
        self._parser = parser

    async def process(self, session: AsyncSession, job: dict) -> None:
        asset_id = job["asset_id"]
        version = await session.scalar(
            select(KnowledgeVersion).where(KnowledgeVersion.id == job["asset_version_id"])
        )
        if not version:
            raise ValueError(f"KnowledgeVersion {job['asset_version_id']} not found")

        await self.mark_processing(session, asset_id)
        temp_path = await _write_temp_file(self._settings, self._storage_reader, version.storage_path)
        try:
            chunks = await self._parser.process_file(
                temp_path,
                job["workspace_id"],
                asset_id,
                job["asset_version_id"],
            )
            if not chunks:
                raise ValueError("Knowledge asset produced no chunks to index")

            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_version_id == job["asset_version_id"])
            )
            session.add_all(chunks)
        finally:
            _remove_file(temp_path)

        await self.mark_ready(session, asset_id)

    async def mark_processing(self, session: AsyncSession, asset_id) -> None:
        await session.execute(
            text("UPDATE knowledge_assets SET status = 'processing', updated_at = NOW() WHERE id = :id"),
            {"id": asset_id},
        )

    async def mark_ready(self, session: AsyncSession, asset_id) -> None:
        await session.execute(
            text("UPDATE knowledge_assets SET status = 'ready', updated_at = NOW() WHERE id = :id"),
            {"id": asset_id},
        )

    async def mark_failed(self, session: AsyncSession, asset_id) -> None:
        await session.execute(
            text("UPDATE knowledge_assets SET status = 'failed', updated_at = NOW() WHERE id = :id"),
            {"id": asset_id},
        )


def _remove_file(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


async def _write_temp_file(settings, storage_reader: StorageReader, storage_path: str) -> str:
    suffix = os.path.splitext(storage_path)[1]
    temp_path = os.path.join(settings.storage_local_path, "tmp", f"{uuid4()}{suffix}")
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    content = await storage_reader.read(storage_path)
    with open(temp_path, "wb") as file:
        file.write(content)
    return temp_path
