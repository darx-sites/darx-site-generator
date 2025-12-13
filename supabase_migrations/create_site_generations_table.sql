-- Create table for tracking DARX site generations
CREATE TABLE IF NOT EXISTS darx_site_generations (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    project_name TEXT NOT NULL,
    industry TEXT NOT NULL,
    components_generated INTEGER NOT NULL DEFAULT 0,
    files_generated INTEGER NOT NULL DEFAULT 0,
    generation_time_seconds DECIMAL(10, 2) NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    deployment_url TEXT,
    build_state TEXT,
    build_logs TEXT
);

-- Create index on project_name for faster lookups
CREATE INDEX idx_site_generations_project_name ON darx_site_generations(project_name);

-- Create index on created_at for time-based queries
CREATE INDEX idx_site_generations_created_at ON darx_site_generations(created_at DESC);

-- Create index on success for filtering failed builds
CREATE INDEX idx_site_generations_success ON darx_site_generations(success);

-- Enable Row Level Security
ALTER TABLE darx_site_generations ENABLE ROW LEVEL SECURITY;

-- Create policy to allow service role full access
CREATE POLICY "Service role has full access to site generations"
ON darx_site_generations
FOR ALL
USING (auth.jwt() ->> 'role' = 'service_role');

-- Grant permissions to service role
GRANT ALL ON darx_site_generations TO service_role;
GRANT USAGE, SELECT ON SEQUENCE darx_site_generations_id_seq TO service_role;

-- Add helpful comments
COMMENT ON TABLE darx_site_generations IS 'Tracks all DARX website generation attempts with build results';
COMMENT ON COLUMN darx_site_generations.project_name IS 'Name of the generated project (e.g., acme-corp)';
COMMENT ON COLUMN darx_site_generations.industry IS 'Industry type (real-estate, saas, ecommerce, etc.)';
COMMENT ON COLUMN darx_site_generations.components_generated IS 'Number of React components generated';
COMMENT ON COLUMN darx_site_generations.files_generated IS 'Total number of files generated';
COMMENT ON COLUMN darx_site_generations.generation_time_seconds IS 'Time taken to complete generation in seconds';
COMMENT ON COLUMN darx_site_generations.success IS 'Whether the generation and deployment succeeded';
COMMENT ON COLUMN darx_site_generations.error_message IS 'Error message if generation failed';
COMMENT ON COLUMN darx_site_generations.deployment_url IS 'Vercel staging URL if deployed successfully';
COMMENT ON COLUMN darx_site_generations.build_state IS 'Vercel build state (READY, ERROR, BUILDING, etc.)';
COMMENT ON COLUMN darx_site_generations.build_logs IS 'Vercel build error logs if build failed';
