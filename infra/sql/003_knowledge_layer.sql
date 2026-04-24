-- Knowledge Base Layer Tables
CREATE TABLE IF NOT EXISTS knowledge_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, processing, ready, failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_asset_id UUID NOT NULL REFERENCES knowledge_assets(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    storage_backend TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_version_id UUID NOT NULL REFERENCES knowledge_versions(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(768), -- Matching nomic-embed-text or similar embedding dimension
    metadata_json JSONB DEFAULT '{}'::jsonb,
    chunk_index INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_knowledge_chunk UNIQUE (knowledge_version_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_assets_workspace_id ON knowledge_assets(workspace_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_version_id ON knowledge_chunks(knowledge_version_id);

-- Update Ingestion Jobs for Dual Lane
ALTER TABLE ingestion_jobs ALTER COLUMN dataset_id DROP NOT NULL;
ALTER TABLE ingestion_jobs ALTER COLUMN dataset_version_id DROP NOT NULL;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS knowledge_asset_id UUID REFERENCES knowledge_assets(id) ON DELETE CASCADE;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS knowledge_version_id UUID REFERENCES knowledge_versions(id) ON DELETE CASCADE;
