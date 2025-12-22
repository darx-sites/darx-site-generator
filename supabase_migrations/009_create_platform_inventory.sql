-- Migration: 009_create_platform_inventory.sql
-- Description: Multiplatform resource tracking with orphan detection
-- Created: 2025-12-19

-- Create platform_inventory table
CREATE TABLE IF NOT EXISTS platform_inventory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Resource identification
    platform TEXT NOT NULL, -- 'github', 'vercel', 'builder', 'gcs', 'supabase'
    resource_type TEXT NOT NULL, -- 'repository', 'project', 'space', 'backup', 'client'
    resource_id TEXT NOT NULL, -- Platform-specific identifier
    resource_name TEXT NOT NULL, -- Human-readable name (e.g., 'test-client-1')

    -- Association
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    client_slug TEXT, -- Denormalized for quick lookups

    -- Resource metadata
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ DEFAULT NOW(),
    resource_metadata JSONB, -- Platform-specific details

    -- Status tracking
    is_orphaned BOOLEAN DEFAULT FALSE, -- In platform but no matching client
    is_drift BOOLEAN DEFAULT FALSE, -- In DB but not in platform
    verification_error TEXT, -- Error message if verification failed

    -- URLs and links
    resource_url TEXT,

    CONSTRAINT unique_platform_resource UNIQUE (platform, resource_type, resource_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_inventory_platform ON platform_inventory(platform);
CREATE INDEX IF NOT EXISTS idx_inventory_client_id ON platform_inventory(client_id);
CREATE INDEX IF NOT EXISTS idx_inventory_client_slug ON platform_inventory(client_slug);
CREATE INDEX IF NOT EXISTS idx_inventory_orphaned ON platform_inventory(is_orphaned)
WHERE is_orphaned = TRUE;
CREATE INDEX IF NOT EXISTS idx_inventory_drift ON platform_inventory(is_drift)
WHERE is_drift = TRUE;
CREATE INDEX IF NOT EXISTS idx_inventory_last_verified ON platform_inventory(last_verified_at);

-- Create composite index for platform + resource queries
CREATE INDEX IF NOT EXISTS idx_inventory_platform_resource
ON platform_inventory(platform, resource_type, resource_name);

-- Create function to mark resources as orphaned
CREATE OR REPLACE FUNCTION mark_orphaned_resources()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    -- Mark resources as orphaned if they have no matching client
    UPDATE platform_inventory
    SET is_orphaned = TRUE
    WHERE client_id IS NULL
    AND is_orphaned = FALSE;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to sync inventory with client
CREATE OR REPLACE FUNCTION sync_inventory_client(p_client_slug TEXT)
RETURNS VOID AS $$
DECLARE
    v_client_id UUID;
BEGIN
    -- Get client ID
    SELECT id INTO v_client_id
    FROM clients
    WHERE client_slug = p_client_slug;

    -- Update all inventory items for this client slug
    UPDATE platform_inventory
    SET client_id = v_client_id,
        is_orphaned = FALSE,
        last_verified_at = NOW()
    WHERE client_slug = p_client_slug;
END;
$$ LANGUAGE plpgsql;

-- Add comments
COMMENT ON TABLE platform_inventory IS 'Complete inventory of resources across all platforms with orphan detection';
COMMENT ON COLUMN platform_inventory.is_orphaned IS 'Resource exists in platform but has no matching client (needs cleanup)';
COMMENT ON COLUMN platform_inventory.is_drift IS 'Resource in DB but not found in platform (stale data)';
COMMENT ON COLUMN platform_inventory.resource_metadata IS 'Platform-specific details (commit SHAs, deployment IDs, etc.)';
COMMENT ON FUNCTION mark_orphaned_resources IS 'Automated function to identify orphaned resources needing cleanup';
COMMENT ON FUNCTION sync_inventory_client IS 'Sync inventory items with correct client after changes';
