CREATE TABLE IF NOT EXISTS chunks (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding vector(768) NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}',
  source_page INTEGER,
  section_title TEXT,
  content_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (dataset_version_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_workspace_id ON chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chunks_dataset_id ON chunks(dataset_id);
CREATE INDEX IF NOT EXISTS idx_chunks_dataset_version_id ON chunks(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
