DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relname = 'knowledge_chunks'
          AND a.attname = 'embedding'
          AND format_type(a.atttypid, a.atttypmod) <> 'vector(768)'
    ) THEN
        UPDATE knowledge_chunks
        SET embedding = NULL
        WHERE embedding IS NOT NULL;

        ALTER TABLE knowledge_chunks
        ALTER COLUMN embedding TYPE VECTOR(768)
        USING NULL;
    END IF;
END;
$migration$;
--;;
