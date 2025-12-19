-- Migration: Add Builder.io Shared Space Support
-- Purpose: Enable multi-tenant Builder.io space architecture for entry-tier clients
-- Date: 2025-12-15
-- Reference: /Users/marvinromero/.claude/plans/elegant-drifting-hollerith.md

-- ============================================================================
-- STEP 1: Add Builder.io space tracking columns to clients table
-- ============================================================================

-- Track which clients use shared vs dedicated Builder.io spaces
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS builder_space_mode TEXT DEFAULT 'DEDICATED',
ADD COLUMN IF NOT EXISTS builder_shared_space_id TEXT,
ADD COLUMN IF NOT EXISTS builder_space_tier TEXT DEFAULT 'entry';

COMMENT ON COLUMN clients.builder_space_mode IS 'SHARED (multi-tenant) or DEDICATED (own space)';
COMMENT ON COLUMN clients.builder_shared_space_id IS 'Reference to shared space ID (null if DEDICATED)';
COMMENT ON COLUMN clients.builder_space_tier IS 'Client tier: entry, premium, enterprise';

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_clients_builder_space_mode ON clients(builder_space_mode);
CREATE INDEX IF NOT EXISTS idx_clients_builder_tier ON clients(builder_space_tier);

-- ============================================================================
-- STEP 2: Create builderio_shared_spaces table
-- ============================================================================

-- Registry of shared Builder.io spaces (one per tier)
CREATE TABLE IF NOT EXISTS builderio_shared_spaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_name TEXT NOT NULL,
    space_id TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL UNIQUE,
    private_key_secret_name TEXT NOT NULL,
    gcp_project_id TEXT NOT NULL DEFAULT 'sylvan-journey-474401-f9',
    tier TEXT NOT NULL,
    max_clients INTEGER,
    active_clients INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE builderio_shared_spaces IS 'Registry of shared multi-tenant Builder.io spaces';
COMMENT ON COLUMN builderio_shared_spaces.space_name IS 'Human-readable name (e.g., "DARX Entry Tier Shared")';
COMMENT ON COLUMN builderio_shared_spaces.space_id IS 'Builder.io space identifier';
COMMENT ON COLUMN builderio_shared_spaces.public_key IS 'Builder.io public API key';
COMMENT ON COLUMN builderio_shared_spaces.private_key_secret_name IS 'GCP Secret Manager secret name for private key';
COMMENT ON COLUMN builderio_shared_spaces.tier IS 'Client tier this space serves (entry, premium, enterprise)';
COMMENT ON COLUMN builderio_shared_spaces.max_clients IS 'Maximum clients allowed (null = unlimited)';
COMMENT ON COLUMN builderio_shared_spaces.active_clients IS 'Current number of active clients using this space';
COMMENT ON COLUMN builderio_shared_spaces.status IS 'Space status: active, disabled, full';

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_shared_spaces_tier ON builderio_shared_spaces(tier);
CREATE INDEX IF NOT EXISTS idx_shared_spaces_status ON builderio_shared_spaces(status);

-- ============================================================================
-- STEP 3: Create builderio_query_audit table for security monitoring
-- ============================================================================

-- Audit log for Builder.io queries to detect cross-tenant leakage attempts
CREATE TABLE IF NOT EXISTS builderio_query_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operation TEXT NOT NULL,
    model TEXT NOT NULL,
    client_slug TEXT,
    has_client_slug_filter BOOLEAN NOT NULL,
    security_level TEXT NOT NULL,  -- 'SAFE' or 'UNSAFE'
    url_path TEXT,
    space_mode TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE builderio_query_audit IS 'Security audit log for Builder.io content queries';
COMMENT ON COLUMN builderio_query_audit.operation IS 'Operation type: get_content, list_content, create_content, etc.';
COMMENT ON COLUMN builderio_query_audit.model IS 'Builder.io model: client_page, page, client_section, etc.';
COMMENT ON COLUMN builderio_query_audit.client_slug IS 'Client identifier extracted from query';
COMMENT ON COLUMN builderio_query_audit.has_client_slug_filter IS 'Whether query included client_slug filter';
COMMENT ON COLUMN builderio_query_audit.security_level IS 'SAFE (properly scoped) or UNSAFE (missing client_slug)';
COMMENT ON COLUMN builderio_query_audit.space_mode IS 'SHARED or DEDICATED';

-- Add indexes for security monitoring
CREATE INDEX IF NOT EXISTS idx_audit_security_level ON builderio_query_audit(security_level);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON builderio_query_audit(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_client_slug ON builderio_query_audit(client_slug);

-- ============================================================================
-- STEP 4: Create monitoring view for unsafe queries
-- ============================================================================

-- Alert view for monitoring cross-tenant leakage attempts
CREATE OR REPLACE VIEW unsafe_builderio_queries AS
SELECT
    id,
    timestamp,
    operation,
    model,
    client_slug,
    has_client_slug_filter,
    url_path,
    space_mode
FROM builderio_query_audit
WHERE security_level = 'UNSAFE'
ORDER BY timestamp DESC;

COMMENT ON VIEW unsafe_builderio_queries IS 'Real-time view of potentially dangerous Builder.io queries missing client_slug filter';

-- ============================================================================
-- STEP 5: Create helper function to increment active_clients counter
-- ============================================================================

-- Function to safely increment/decrement active_clients counter
CREATE OR REPLACE FUNCTION update_shared_space_client_count(
    space_uuid UUID,
    delta INTEGER
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    new_count INTEGER;
BEGIN
    UPDATE builderio_shared_spaces
    SET
        active_clients = GREATEST(0, active_clients + delta),
        updated_at = NOW()
    WHERE id = space_uuid
    RETURNING active_clients INTO new_count;

    RETURN new_count;
END;
$$;

COMMENT ON FUNCTION update_shared_space_client_count IS 'Safely increment/decrement active_clients counter for shared spaces';

-- ============================================================================
-- STEP 6: Migration Notes
-- ============================================================================

-- IMPORTANT: After running this migration:
-- 1. Manually create Builder.io Space at https://builder.io
-- 2. Configure content models (client_page, client_section) with required client_slug field
-- 3. Run setup_shared_space.py to register space credentials
-- 4. Update provisioner, site-generator, and darx-reasoning-function code
-- 5. Configure wildcard DNS: *.darx.site → cname.vercel-dns.com
-- 6. Test with new entry-tier client
-- 7. Monitor unsafe_builderio_queries view for 48 hours

-- Query to verify migration:
-- SELECT
--     column_name,
--     data_type,
--     is_nullable,
--     column_default
-- FROM information_schema.columns
-- WHERE table_name = 'clients'
--   AND column_name LIKE '%builder%'
-- ORDER BY ordinal_position;
