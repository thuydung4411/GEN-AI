import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from api.app.db.base import Base


class DatasetStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class AssetKind(str, enum.Enum):
    dataset = "dataset"
    knowledge = "knowledge"


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class MessageStatus(str, enum.Enum):
    streaming = "streaming"
    completed = "completed"
    failed = "failed"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members: Mapped[list["WorkspaceMember"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    knowledge_assets: Mapped[list["KnowledgeAsset"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(64), default="owner", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="members")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DatasetStatus] = mapped_column(Enum(DatasetStatus, name="dataset_status"), default=DatasetStatus.pending, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped[Workspace] = relationship(back_populates="datasets")
    versions: Mapped[list["DatasetVersion"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")
    jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="versions")
    sheets: Mapped[list["DatasetSheet"]] = relationship(back_populates="version", cascade="all, delete-orphan")
    column_profiles: Mapped[list["ColumnProfile"]] = relationship(back_populates="version", cascade="all, delete-orphan")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="dataset_version", cascade="all, delete-orphan")


class DatasetSheet(Base):
    __tablename__ = "dataset_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False)
    asset_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(nullable=False)
    row_count: Mapped[int | None] = mapped_column()
    column_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    version: Mapped["DatasetVersion"] = relationship(back_populates="sheets")


class ColumnProfile(Base):
    __tablename__ = "column_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False)
    asset_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"))
    sheet_name: Mapped[str | None] = mapped_column()
    column_name: Mapped[str] = mapped_column(nullable=False)
    data_type: Mapped[str] = mapped_column(nullable=False)
    null_count: Mapped[int | None] = mapped_column()
    distinct_count: Mapped[int | None] = mapped_column()
    min_value: Mapped[str | None] = mapped_column()
    max_value: Mapped[str | None] = mapped_column()
    sample_values: Mapped[dict | None] = mapped_column(type_=JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    version: Mapped["DatasetVersion"] = relationship(back_populates="column_profiles")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    asset_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"))
    asset_kind: Mapped[AssetKind | None] = mapped_column(Enum(AssetKind, name="asset_kind"))
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dataset_versions.id", ondelete="CASCADE"))
    knowledge_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_assets.id", ondelete="CASCADE"))
    knowledge_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_versions.id", ondelete="CASCADE"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), default=JobStatus.pending, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1024))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    dataset: Mapped[Dataset] = relationship(back_populates="jobs")
    dataset_version: Mapped["DatasetVersion"] = relationship()
    knowledge_asset: Mapped["KnowledgeAsset"] = relationship(back_populates="jobs")
    knowledge_version: Mapped["KnowledgeVersion"] = relationship()
    asset: Mapped["Asset"] = relationship(back_populates="jobs")
    asset_version: Mapped["AssetVersion"] = relationship()


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("dataset_version_id", "chunk_index", name="uq_chunk_version_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    asset_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_versions.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, server_default='{}', nullable=False)
    source_page: Mapped[int | None] = mapped_column(nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="chunks")
    dataset: Mapped[Dataset] = relationship(back_populates="chunks")
    dataset_version: Mapped[DatasetVersion] = relationship(back_populates="chunks")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[AssetKind] = mapped_column(Enum(AssetKind, name="asset_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DatasetStatus] = mapped_column(Enum(DatasetStatus, name="dataset_status"), default=DatasetStatus.pending, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    workspace: Mapped[Workspace] = relationship(back_populates="assets")
    versions: Mapped[list["AssetVersion"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (UniqueConstraint("asset_id", "version_number", name="uq_asset_version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset: Mapped[Asset] = relationship(back_populates="versions")


class KnowledgeAsset(Base):
    __tablename__ = "knowledge_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DatasetStatus] = mapped_column(Enum(DatasetStatus, name="dataset_status"), default=DatasetStatus.pending, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    workspace: Mapped[Workspace] = relationship(back_populates="knowledge_assets")
    versions: Mapped[list["KnowledgeVersion"]] = relationship(back_populates="knowledge_asset", cascade="all, delete-orphan")
    jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="knowledge_asset", cascade="all, delete-orphan")


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (UniqueConstraint("knowledge_asset_id", "version_number", name="uq_knowledge_version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_assets.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    knowledge_asset: Mapped[KnowledgeAsset] = relationship(back_populates="versions")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="knowledge_version", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("knowledge_version_id", "chunk_index", name="uq_knowledge_chunk_version_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_versions.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, server_default='{}', nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    knowledge_version: Mapped[KnowledgeVersion] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    workspace: Mapped[Workspace] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(String, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieval_used: Mapped[bool] = mapped_column(default=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
