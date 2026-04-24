-- Table for different sheets within an Excel dataset
CREATE TABLE IF NOT EXISTS dataset_sheets (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    row_count INTEGER,
    column_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_version_id, name)
);

-- Table for statistical profiles of columns
CREATE TABLE IF NOT EXISTS column_profiles (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    sheet_name TEXT, -- Null for CSV, or sheet name for Excel
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    null_count INTEGER,
    distinct_count INTEGER,
    min_value TEXT,
    max_value TEXT,
    sample_values JSONB, -- Small sample of values
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_sheets_version ON dataset_sheets(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_column_profiles_version ON column_profiles(dataset_version_id);

-- Update ingestion_jobs to support knowledge lane
ALTER TABLE ingestion_jobs 
    ALTER COLUMN dataset_id DROP NOT NULL,
    ALTER COLUMN dataset_version_id DROP NOT NULL;

ALTER TABLE ingestion_jobs
    ADD COLUMN IF NOT EXISTS knowledge_asset_id UUID REFERENCES knowledge_assets(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS knowledge_version_id UUID REFERENCES knowledge_versions(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_knowledge_asset_id ON ingestion_jobs(knowledge_asset_id);
