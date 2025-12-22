-- Migration: 010_create_registry_operations_log.sql
-- Description: Complete audit trail for all site operations
-- Created: 2025-12-19

-- Create registry_operations_log table
CREATE TABLE IF NOT EXISTS registry_operations_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Operation metadata
    operation_type TEXT NOT NULL, -- 'create', 'update', 'delete', 'recover', 'health_check', 'deploy'
    operation_status TEXT NOT NULL, -- 'started', 'in_progress', 'success', 'failed', 'partial_success'

    -- Target resource
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    client_slug TEXT NOT NULL,

    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Who/what initiated
    initiated_by TEXT NOT NULL, -- 'darx', 'admin', user ID, 'system'
    trigger_source TEXT, -- 'api', 'function_call', 'scheduled', 'manual'

    -- Platform-specific results
    github_result JSONB,
    vercel_result JSONB,
    builder_result JSONB,
    gcs_result JSONB,
    supabase_result JSONB,

    -- Overall result
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    error_messages TEXT[],

    -- Rollback tracking
    can_rollback BOOLEAN DEFAULT FALSE,
    rolled_back BOOLEAN DEFAULT FALSE,
    rollback_operation_id UUID REFERENCES registry_operations_log(id),

    -- Additional context
    request_payload JSONB, -- Original request data
    response_payload JSONB, -- Final response data
    notes TEXT,

    CONSTRAINT check_operation_type
    CHECK (operation_type IN ('create', 'update', 'delete', 'recover', 'health_check', 'deploy', 'rollback', 'inventory_sync')),

    CONSTRAINT check_operation_status
    CHECK (operation_status IN ('started', 'in_progress', 'success', 'failed', 'partial_success', 'rolled_back'))
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_operations_client_id ON registry_operations_log(client_id);
CREATE INDEX IF NOT EXISTS idx_operations_client_slug ON registry_operations_log(client_slug);
CREATE INDEX IF NOT EXISTS idx_operations_started_at ON registry_operations_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_operations_type ON registry_operations_log(operation_type);
CREATE INDEX IF NOT EXISTS idx_operations_status ON registry_operations_log(operation_status);
CREATE INDEX IF NOT EXISTS idx_operations_initiated_by ON registry_operations_log(initiated_by);

-- Composite index for finding recent operations for a client
CREATE INDEX IF NOT EXISTS idx_operations_client_recent
ON registry_operations_log(client_slug, started_at DESC);

-- Create function to automatically calculate duration
CREATE OR REPLACE FUNCTION calculate_operation_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for duration calculation
DROP TRIGGER IF EXISTS trigger_calculate_duration ON registry_operations_log;
CREATE TRIGGER trigger_calculate_duration
    BEFORE UPDATE ON registry_operations_log
    FOR EACH ROW
    WHEN (NEW.completed_at IS DISTINCT FROM OLD.completed_at)
    EXECUTE FUNCTION calculate_operation_duration();

-- Create function to get operation history for a client
CREATE OR REPLACE FUNCTION get_client_operation_history(
    p_client_slug TEXT,
    p_limit INTEGER DEFAULT 50
)
RETURNS TABLE (
    operation_type TEXT,
    operation_status TEXT,
    started_at TIMESTAMPTZ,
    duration_ms INTEGER,
    initiated_by TEXT,
    success_count INTEGER,
    failure_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.operation_type,
        l.operation_status,
        l.started_at,
        l.duration_ms,
        l.initiated_by,
        l.success_count,
        l.failure_count
    FROM registry_operations_log l
    WHERE l.client_slug = p_client_slug
    ORDER BY l.started_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Add comments
COMMENT ON TABLE registry_operations_log IS 'Complete audit trail of all operations across all platforms';
COMMENT ON COLUMN registry_operations_log.operation_status IS 'partial_success = some platforms succeeded, some failed';
COMMENT ON COLUMN registry_operations_log.can_rollback IS 'Whether this operation supports rollback';
COMMENT ON COLUMN registry_operations_log.rollback_operation_id IS 'References the operation that rolled this one back';
COMMENT ON FUNCTION get_client_operation_history IS 'Get recent operation history for troubleshooting';
