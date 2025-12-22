-- Migration: 006_create_site_deployments.sql
-- Description: Track deployment history for rollback capability
-- Created: 2025-12-19

-- Create site_deployments table
CREATE TABLE IF NOT EXISTS site_deployments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Deployment identifiers
    commit_sha TEXT NOT NULL,
    vercel_deployment_id TEXT,

    -- Deployment metadata
    deployed_at TIMESTAMPTZ DEFAULT NOW(),
    deployed_by TEXT NOT NULL, -- 'darx', 'manual', or user identifier
    deployment_trigger TEXT, -- 'regeneration', 'update', 'initial', 'rollback'

    -- Deployment status
    status TEXT NOT NULL DEFAULT 'in_progress',
    build_state TEXT, -- Vercel build state: 'READY', 'ERROR', 'BUILDING', etc.
    build_logs TEXT, -- Error logs if build failed

    -- URLs
    staging_url TEXT,
    production_url TEXT,

    -- Rollback tracking
    rolled_back BOOLEAN DEFAULT FALSE,
    rolled_back_at TIMESTAMPTZ,
    rollback_reason TEXT,

    CONSTRAINT check_deployment_status
    CHECK (status IN ('in_progress', 'success', 'failed', 'canceled', 'rolled_back'))
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_deployments_client_id ON site_deployments(client_id);
CREATE INDEX IF NOT EXISTS idx_deployments_deployed_at ON site_deployments(deployed_at DESC);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON site_deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployments_vercel_id ON site_deployments(vercel_deployment_id);

-- Composite index for finding latest successful deployment
CREATE INDEX IF NOT EXISTS idx_deployments_client_success
ON site_deployments(client_id, deployed_at DESC)
WHERE status = 'success' AND rolled_back = FALSE;

-- Add comments
COMMENT ON TABLE site_deployments IS 'Complete deployment history for all client sites';
COMMENT ON COLUMN site_deployments.deployed_by IS 'Who initiated: darx (automated), manual (user), or specific user ID';
COMMENT ON COLUMN site_deployments.deployment_trigger IS 'What triggered deployment: regeneration, update, initial, rollback';
COMMENT ON COLUMN site_deployments.build_state IS 'Vercel-specific build state for debugging';
