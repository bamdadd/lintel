-- Add gdrive_source_url to compliance policies for Google Drive import traceability.
--
-- Stores the originating Google Drive URL when a policy description was imported
-- from a Google Drive document.
ALTER TABLE compliance_policies ADD COLUMN IF NOT EXISTS gdrive_source_url TEXT;
