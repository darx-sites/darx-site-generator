-- Migration: 005_enhance_clients_table.sql
-- Description: Add columns for health monitoring, deletion tracking, and extensibility
-- Created: 2025-12-19

-- Add new columns to clients table
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS health_status TEXT DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS last_health_check_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS vercel_project_id TEXT,
ADD COLUMN IF NOT EXISTS deletion_scheduled_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Create index for health status queries
CREATE INDEX IF NOT EXISTS idx_clients_health_status ON clients(health_status);

-- Create index for deletion tracking
CREATE INDEX IF NOT EXISTS idx_clients_deletion_scheduled ON clients(deletion_scheduled_at)
WHERE deletion_scheduled_at IS NOT NULL;

-- Add check constraint for valid health statuses
ALTER TABLE clients
DROP CONSTRAINT IF EXISTS check_health_status;

ALTER TABLE clients
ADD CONSTRAINT check_health_status
CHECK (health_status IN ('healthy', 'degraded', 'down', 'unknown'));

-- Add comment documentation
COMMENT ON COLUMN clients.health_status IS 'Current overall health status: healthy, degraded, down, unknown';
COMMENT ON COLUMN clients.last_health_check_at IS 'Timestamp of last automated health check';
COMMENT ON COLUMN clients.vercel_project_id IS 'Vercel project identifier for deployment tracking';
COMMENT ON COLUMN clients.deletion_scheduled_at IS 'Timestamp when soft delete was initiated (NULL if not deleted)';
COMMENT ON COLUMN clients.tags IS 'Array of custom tags for organization and filtering';
COMMENT ON COLUMN clients.metadata IS 'Extensible JSON field for additional client-specific data';
