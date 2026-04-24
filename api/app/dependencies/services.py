from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.repositories.interfaces import DatasetRepository, KnowledgeRepository, ChatRepository, AssetRepository
from api.app.repositories.sqlalchemy import SqlAlchemyDatasetRepository, SqlAlchemyKnowledgeRepository, SqlAlchemyAssetRepository
from api.app.repositories.chat import SqlAlchemyChatRepository
from api.app.services.datasets import DatasetService
from api.app.services.knowledge import KnowledgeService
from api.app.services.storage import StorageService, build_storage_service
from api.app.services.embedder import QueryEmbedder
from api.app.services.rag import RAGService
from api.app.services.chat import ChatService
from api.app.services.assets import AssetService
from api.app.services.parsers.tabular import TabularParser


def get_repository(session: AsyncSession = Depends(get_db_session)) -> DatasetRepository:
    return SqlAlchemyDatasetRepository(session)


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    return build_storage_service(settings)


def get_tabular_parser(settings: Settings = Depends(get_settings)) -> TabularParser:
    return TabularParser(storage_root=settings.storage_local_path)


def get_dataset_service(
    repository: DatasetRepository = Depends(get_repository),
    storage_service: StorageService = Depends(get_storage_service),
    settings: Settings = Depends(get_settings),
    tabular_parser: TabularParser = Depends(get_tabular_parser),
) -> DatasetService:
    return DatasetService(
        repository=repository, 
        storage_service=storage_service, 
        settings=settings,
        tabular_parser=tabular_parser
    )

def get_chat_repository(session: AsyncSession = Depends(get_db_session)) -> ChatRepository:
    return SqlAlchemyChatRepository(session)

def get_query_embedder(settings: Settings = Depends(get_settings)) -> QueryEmbedder:
    return QueryEmbedder(settings)

def get_rag_service(
    settings: Settings = Depends(get_settings),
    embedder: QueryEmbedder = Depends(get_query_embedder),
    session: AsyncSession = Depends(get_db_session)
) -> RAGService:
    return RAGService(settings=settings, embedder=embedder, session=session)

def get_knowledge_repository(session: AsyncSession = Depends(get_db_session)) -> KnowledgeRepository:
    return SqlAlchemyKnowledgeRepository(session)


def get_knowledge_service(
    repository: KnowledgeRepository = Depends(get_knowledge_repository),
    storage_service: StorageService = Depends(get_storage_service),
    settings: Settings = Depends(get_settings),
) -> KnowledgeService:
    return KnowledgeService(repository=repository, storage_service=storage_service, settings=settings)


def get_chat_service(
    repository: DatasetRepository = Depends(get_repository),
    chat_repository: ChatRepository = Depends(get_chat_repository),
    rag_service: RAGService = Depends(get_rag_service),
) -> ChatService:
    return ChatService(repository=repository, chat_repository=chat_repository, rag_service=rag_service)


def get_asset_repository(session: AsyncSession = Depends(get_db_session)) -> AssetRepository:
    return SqlAlchemyAssetRepository(session)


def get_asset_service(
    repo: AssetRepository = Depends(get_asset_repository),
    dataset_service: DatasetService = Depends(get_dataset_service),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> AssetService:
    return AssetService(repo, dataset_service, knowledge_service)
