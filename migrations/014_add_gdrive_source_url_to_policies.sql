-- Add gdrive_source_url to compliance policies for Google Drive import traceability.
--
-- Stores the originating Google Drive URL when a policy description was imported
-- from a Google Drive document.
-- compliance_policies may not exist as a dedicated table (stored in JSONB dict store).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'compliance_policies') THEN
        ALTER TABLE compliance_policies ADD COLUMN IF NOT EXISTS gdrive_source_url TEXT;
    END IF;
END
$$;
