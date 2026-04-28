import asyncio
import logging
import traceback
import os
from uuid import uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from worker.app.core.settings import get_settings
from worker.app.services.storage import StorageReader
from api.app.services.parsers.tabular import TabularParser
from api.app.services.parsers.knowledge import KnowledgeParser
from api.app.models.entities import (
    Dataset, DatasetStatus, DatasetVersion, KnowledgeVersion, 
    IngestionJob, JobStatus, DatasetSheet, ColumnProfile, KnowledgeChunk,
    Asset, AssetVersion, AssetKind
)

logger = logging.getLogger(__name__)


async def claim_next_job(session: AsyncSession):
    claim_sql = text("""
        UPDATE ingestion_jobs
        SET status = :processing_status, updated_at = NOW()
        WHERE id = (
            SELECT id FROM ingestion_jobs
            WHERE status = :pending_status
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, asset_id, asset_version_id, asset_kind, workspace_id, dataset_id, dataset_version_id, knowledge_asset_id, knowledge_version_id;
    """)
    result = await session.execute(claim_sql, {
        "processing_status": JobStatus.processing.value,
        "pending_status": JobStatus.pending.value
    })
    row = result.fetchone()
    if row:
        await session.commit()
        return dict(row._mapping)
    return None

async def process_job(
    settings,
    job_info: dict,
    session_maker,
    storage_reader: StorageReader,
    tabular_parser: TabularParser,
    knowledge_parser: KnowledgeParser,
):
    job_id = job_info["id"]
    workspace_id = job_info["workspace_id"]
    
    try:
        async with session_maker() as session:
            # 1. Determine lane from asset_kind
            kind = job_info.get("asset_kind")
            asset_id = job_info.get("asset_id")
            version_id = job_info.get("asset_version_id")
            
            # Fallback for legacy jobs during transition
            if not kind:
                if job_info.get("dataset_id"):
                    kind = AssetKind.dataset
                    asset_id = job_info["dataset_id"]
                    version_id = job_info["dataset_version_id"]
                else:
                    kind = AssetKind.knowledge
                    asset_id = job_info["knowledge_asset_id"]
                    version_id = job_info["knowledge_version_id"]

            if not asset_id:
                raise ValueError(f"Job {job_id} has no asset_id and no legacy IDs")

            # Set Asset and Job to processing
            await session.execute(text("UPDATE assets SET status = 'processing', updated_at = NOW() WHERE id = :id"), {"id": asset_id})
            
            if kind == AssetKind.dataset:
                # Structured Lane
                stmt_v = select(DatasetVersion).where(DatasetVersion.id == version_id)
                version = await session.scalar(stmt_v)
                if not version:
                    raise ValueError(f"DatasetVersion {version_id} not found")

                # Sync legacy status
                await session.execute(text("UPDATE datasets SET status = 'processing', updated_at = NOW() WHERE id = :id"), {"id": asset_id})

                logger.info(f"Processing Dataset {asset_id}")
                temp_path = os.path.join(settings.storage_local_path, "tmp", str(uuid4()))
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                content = await storage_reader.read(version.storage_path)
                with open(temp_path, "wb") as f:
                    f.write(content)
                
                try:
                    sheets, profiles = tabular_parser.parse_and_materialize(
                        temp_path, workspace_id, asset_id, version_id
                    )
                    await session.execute(delete(DatasetSheet).where(DatasetSheet.dataset_version_id == version_id))
                    await session.execute(delete(ColumnProfile).where(ColumnProfile.dataset_version_id == version_id))
                    session.add_all(sheets)
                    session.add_all(profiles)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                # Update Legacy Status
                await session.execute(text("UPDATE datasets SET status = 'ready' WHERE id = :id"), {"id": asset_id})

            elif kind == AssetKind.knowledge:
                # Unstructured Lane
                stmt_v = select(KnowledgeVersion).where(KnowledgeVersion.id == version_id)
                version = await session.scalar(stmt_v)
                if not version:
                    raise ValueError(f"KnowledgeVersion {version_id} not found")

                # Sync legacy status
                await session.execute(text("UPDATE knowledge_assets SET status = 'processing', updated_at = NOW() WHERE id = :id"), {"id": asset_id})

                logger.info(f"Processing Knowledge Asset {asset_id}")
                temp_extension = os.path.splitext(version.storage_path)[1]
                temp_path = os.path.join(
                    settings.storage_local_path,
                    "tmp",
                    f"{uuid4()}{temp_extension}",
                )
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                content = await storage_reader.read(version.storage_path)
                with open(temp_path, "wb") as f:
                    f.write(content)

                try:
                    chunks = await knowledge_parser.process_file(
                        temp_path, workspace_id, asset_id, version_id
                    )
                    if not chunks:
                        raise ValueError("Knowledge asset produced no chunks to index")
                    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_version_id == version_id))
                    session.add_all(chunks)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                # Update Legacy Status
                await session.execute(text("UPDATE knowledge_assets SET status = 'ready' WHERE id = :id"), {"id": asset_id})

            # Update Unified Asset Status
            await session.execute(text("UPDATE assets SET status = 'ready' WHERE id = :id"), {"id": asset_id})

            # Common: Mark Job as Ready
            await session.execute(text("UPDATE ingestion_jobs SET status = 'ready', updated_at = NOW() WHERE id = :id"), {"id": job_id})
            await session.commit()
            logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        error_msg = str(e)[:1000]
        async with session_maker() as session:
            # Simple fail job logic
            await session.execute(text("UPDATE ingestion_jobs SET status = 'failed', error_message = :err WHERE id = :id"), {"id": job_id, "err": error_msg})
            
            asset_id = job_info.get("asset_id") or job_info.get("dataset_id") or job_info.get("knowledge_asset_id")
            if asset_id:
                await session.execute(text("UPDATE assets SET status = 'failed' WHERE id = :id"), {"id": asset_id})
                # Sync legacy systems
                await session.execute(text("UPDATE datasets SET status = 'failed' WHERE id = :id"), {"id": asset_id})
                await session.execute(text("UPDATE knowledge_assets SET status = 'failed' WHERE id = :id"), {"id": asset_id})
            await session.commit()



async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    settings = get_settings()
    
    if settings.worker_mode == "idle":
        logger.info("Worker is in idle mode.")
        while True:
            await asyncio.sleep(60)
            
    logger.info("Starting production worker...")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    storage_reader = StorageReader(settings)
    tabular_parser = TabularParser(storage_root=settings.storage_local_path)
    knowledge_parser = KnowledgeParser(
        gemini_api_key=settings.gemini_api_key,
        ollama_url=settings.ollama_url,
        ollama_embed_model=settings.ollama_embed_model,
        gemini_embed_model=settings.gemini_embed_model,
    )
    
    while True:
        try:
            async with session_maker() as session:
                job_info = await claim_next_job(session)
                
            if job_info:
                logger.info(f"Claimed job: {job_info['id']}")
                await process_job(
                    settings, job_info, session_maker,
                    storage_reader, tabular_parser, knowledge_parser
                )
                continue # Immediately poll next job if we found one
                
        except Exception:
            logger.exception("Error in worker main loop")
            
        await asyncio.sleep(settings.poll_interval_seconds)

if __name__ == "__main__":
    asyncio.run(main())
