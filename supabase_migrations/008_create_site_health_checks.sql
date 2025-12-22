-- Migration: 008_create_site_health_checks.sql
-- Description: Automated health monitoring across all platforms
-- Created: 2025-12-19

-- Create site_health_checks table
CREATE TABLE IF NOT EXISTS site_health_checks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Check metadata
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    check_duration_ms INTEGER, -- How long the check took

    -- Overall status
    overall_status TEXT NOT NULL,

    -- GitHub health
    github_status TEXT,
    github_repo_exists BOOLEAN,
    github_last_commit_at TIMESTAMPTZ,
    github_open_issues_count INTEGER,
    github_details JSONB,

    -- Vercel health
    vercel_status TEXT,
    vercel_deployment_state TEXT, -- 'READY', 'ERROR', etc.
    vercel_ssl_valid BOOLEAN,
    vercel_last_deployment_at TIMESTAMPTZ,
    vercel_details JSONB,

    -- Builder.io health
    builder_status TEXT,
    builder_space_accessible BOOLEAN,
    builder_content_count INTEGER,
    builder_details JSONB,

    -- GCS backup health
    gcs_status TEXT,
    gcs_backup_exists BOOLEAN,
    gcs_latest_backup_at TIMESTAMPTZ,
    gcs_backup_count INTEGER,
    gcs_details JSONB,

    -- Staging URL health
    staging_url_status TEXT,
    staging_url_http_code INTEGER,
    staging_url_response_time_ms INTEGER,
    staging_url_accessible BOOLEAN,
    staging_url_details JSONB,

    CONSTRAINT check_overall_status
    CHECK (overall_status IN ('healthy', 'degraded', 'down', 'error'))
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_health_checks_client_id ON site_health_checks(client_id);
CREATE INDEX IF NOT EXISTS idx_health_checks_checked_at ON site_health_checks(checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_checks_overall_status ON site_health_checks(overall_status);

-- Composite index for latest health check per client
CREATE INDEX IF NOT EXISTS idx_health_checks_latest
ON site_health_checks(client_id, checked_at DESC);

-- Create function to get latest health status for a client
CREATE OR REPLACE FUNCTION get_latest_health(p_client_id UUID)
RETURNS TABLE (
    overall_status TEXT,
    checked_at TIMESTAMPTZ,
    github_status TEXT,
    vercel_status TEXT,
    builder_status TEXT,
    gcs_status TEXT,
    staging_url_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        h.overall_status,
        h.checked_at,
        h.github_status,
        h.vercel_status,
        h.builder_status,
        h.gcs_status,
        h.staging_url_status
    FROM site_health_checks h
    WHERE h.client_id = p_client_id
    ORDER BY h.checked_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Add comments
COMMENT ON TABLE site_health_checks IS 'Automated health monitoring history across all platforms';
COMMENT ON COLUMN site_health_checks.overall_status IS 'Aggregated status: healthy (all OK), degraded (some issues), down (critical failure)';
COMMENT ON COLUMN site_health_checks.check_duration_ms IS 'Performance metric for health check execution time';
COMMENT ON FUNCTION get_latest_health IS 'Helper function to quickly fetch latest health status for a client';
