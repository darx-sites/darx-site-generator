-- Create onboarding_tokens table for persistent token storage
-- Replaces in-memory token storage to survive Cloud Run restarts

CREATE TABLE IF NOT EXISTS onboarding_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT NOT NULL UNIQUE,
    client_slug TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    used_at TIMESTAMPTZ
);

COMMENT ON TABLE onboarding_tokens IS 'Persistent storage for onboarding tokens (24h validity)';
COMMENT ON COLUMN onboarding_tokens.token IS 'Secure random token for onboarding link';
COMMENT ON COLUMN onboarding_tokens.client_slug IS 'Client identifier associated with this token';
COMMENT ON COLUMN onboarding_tokens.used IS 'Whether the token has been consumed';
COMMENT ON COLUMN onboarding_tokens.used_at IS 'Timestamp when token was used';

-- Indexes for efficient queries
CREATE INDEX idx_onboarding_tokens_token ON onboarding_tokens(token);
CREATE INDEX idx_onboarding_tokens_expires_at ON onboarding_tokens(expires_at);
CREATE INDEX idx_onboarding_tokens_used ON onboarding_tokens(used);

-- Auto-delete expired tokens (cleanup job)
CREATE OR REPLACE FUNCTION cleanup_expired_onboarding_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM onboarding_tokens
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup to run daily (requires pg_cron extension)
-- Note: Enable pg_cron in Supabase dashboard first
-- SELECT cron.schedule('cleanup-onboarding-tokens', '0 0 * * *', 'SELECT cleanup_expired_onboarding_tokens()');
