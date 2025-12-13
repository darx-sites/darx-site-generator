-- Migration: Create clients table for DARX onboarding
-- This table stores client information submitted through the onboarding form

CREATE TABLE IF NOT EXISTS clients (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_name TEXT NOT NULL,
    client_slug TEXT NOT NULL UNIQUE,
    contact_email TEXT NOT NULL,
    website_type TEXT NOT NULL,
    builder_public_key TEXT,
    builder_private_key TEXT,  -- TODO: Encrypt in production using Vault
    builder_space_id TEXT,
    industry TEXT,
    status TEXT NOT NULL DEFAULT 'pending_provisioning',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Metadata
    onboarding_token_used TEXT,  -- Track which token was used
    provisioned_at TIMESTAMPTZ,  -- When site was generated
    github_repo TEXT,            -- Generated repo URL
    staging_url TEXT             -- Vercel staging URL
);

-- Create index on client_slug for fast lookups
CREATE INDEX IF NOT EXISTS idx_clients_client_slug ON clients(client_slug);

-- Create index on status for filtering
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);

-- Create index on contact_email for lookups
CREATE INDEX IF NOT EXISTS idx_clients_contact_email ON clients(contact_email);

-- Enable Row Level Security
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

-- Policy: Service role can do everything (for backend API)
CREATE POLICY "Service role full access" ON clients
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE clients IS 'Stores client information from DARX onboarding form';
COMMENT ON COLUMN clients.status IS 'pending_provisioning, provisioning, active, suspended, archived';
COMMENT ON COLUMN clients.builder_private_key IS 'Should be encrypted in production - contains Builder.io private API key';
