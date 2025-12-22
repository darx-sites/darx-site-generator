-- Migration: 007_create_deleted_sites.sql
-- Description: CRITICAL - Soft delete with 30-day recovery window
-- Created: 2025-12-19

-- Create deleted_sites table
CREATE TABLE IF NOT EXISTS deleted_sites (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    original_client_id UUID NOT NULL,

    -- Complete snapshot of client data
    client_data JSONB NOT NULL,

    -- Deletion metadata
    deleted_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_by TEXT NOT NULL, -- Who initiated deletion (darx, admin, user ID)
    deletion_reason TEXT,
    recovery_deadline TIMESTAMPTZ NOT NULL, -- deleted_at + 30 days

    -- Platform deletion status (tracks progress across platforms)
    github_deleted BOOLEAN DEFAULT FALSE,
    github_deletion_result JSONB, -- Stores API response

    vercel_deleted BOOLEAN DEFAULT FALSE,
    vercel_deletion_result JSONB,

    builder_deleted BOOLEAN DEFAULT FALSE,
    builder_deletion_result JSONB,

    gcs_deleted BOOLEAN DEFAULT FALSE,
    gcs_deletion_result JSONB,

    -- Recovery tracking
    recovered BOOLEAN DEFAULT FALSE,
    recovered_at TIMESTAMPTZ,
    recovered_by TEXT,
    new_client_id UUID REFERENCES clients(id), -- New ID if recovered

    -- Permanent deletion
    permanently_deleted BOOLEAN DEFAULT FALSE,
    permanently_deleted_at TIMESTAMPTZ,

    CONSTRAINT check_recovery_deadline
    CHECK (recovery_deadline > deleted_at)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_deleted_sites_recovery_deadline ON deleted_sites(recovery_deadline)
WHERE recovered = FALSE AND permanently_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_deleted_sites_deleted_at ON deleted_sites(deleted_at DESC);

CREATE INDEX IF NOT EXISTS idx_deleted_sites_recovered ON deleted_sites(recovered)
WHERE recovered = TRUE;

CREATE INDEX IF NOT EXISTS idx_deleted_sites_original_id ON deleted_sites(original_client_id);

-- Create function to automatically set recovery deadline
CREATE OR REPLACE FUNCTION set_recovery_deadline()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.recovery_deadline IS NULL THEN
        NEW.recovery_deadline := NEW.deleted_at + INTERVAL '30 days';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to set recovery deadline
DROP TRIGGER IF EXISTS trigger_set_recovery_deadline ON deleted_sites;
CREATE TRIGGER trigger_set_recovery_deadline
    BEFORE INSERT ON deleted_sites
    FOR EACH ROW
    EXECUTE FUNCTION set_recovery_deadline();

-- Add comments
COMMENT ON TABLE deleted_sites IS 'Soft-deleted sites with 30-day recovery window';
COMMENT ON COLUMN deleted_sites.client_data IS 'Complete JSONB snapshot of all client data from clients table';
COMMENT ON COLUMN deleted_sites.recovery_deadline IS 'Automatically set to deleted_at + 30 days';
COMMENT ON COLUMN deleted_sites.github_deletion_result IS 'Stores API response for debugging/audit';
COMMENT ON COLUMN deleted_sites.new_client_id IS 'References new client record if site was recovered';
