# Check Database Schema

## Error: Column 'contact_email' not found

This error suggests the `clients` table schema doesn't match what the form expects.

## Step 1: Verify Table Exists

Run this in Supabase SQL Editor:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'clients';
```

**Expected**: Should return one row with `clients`

---

## Step 2: Check Actual Columns

```sql
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'clients'
ORDER BY ordinal_position;
```

**Expected columns from migration 002**:
- id (uuid)
- client_name (text)
- client_slug (text)
- contact_email (text) ← **MISSING ACCORDING TO ERROR**
- website_type (text)
- builder_public_key (text)
- builder_private_key (text)
- builder_space_id (text)
- industry (text)
- status (text)
- created_at (timestamptz)
- updated_at (timestamptz)
- onboarding_token_used (text)
- provisioned_at (timestamptz)
- github_repo (text)
- staging_url (text)

Plus from migration 003:
- builder_space_mode (text)
- builder_shared_space_id (text)
- builder_space_tier (text)

---

## Step 3: If Columns Are Missing

### Option A: Apply Missing Migrations

If `contact_email` is missing, apply migration 002:

```bash
# File: /Users/marvinromero/darx-site-generator/supabase_migrations/002_create_clients_table.sql
```

Copy the SQL and run it in Supabase SQL Editor.

### Option B: Add Missing Column Manually

If table exists but column is missing:

```sql
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS contact_email TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_clients_contact_email ON clients(contact_email);
```

---

## Step 4: Verify Form Can Insert

After ensuring columns exist, test with this query:

```sql
-- Test insert (will fail if columns still missing)
INSERT INTO clients (
    client_name,
    client_slug,
    contact_email,
    website_type,
    industry,
    builder_space_tier,
    status
) VALUES (
    'Test Client',
    'test-client-999',
    'test@example.com',
    'marketing',
    'Technology',
    'entry',
    'pending_provisioning'
) RETURNING id, client_slug, contact_email;

-- Clean up test data
DELETE FROM clients WHERE client_slug = 'test-client-999';
```

**Expected**: Should insert and return the row, then delete it.

---

## Common Issues

### Issue 1: Wrong Supabase Project

Check your environment variables in Cloud Run:
- `SUPABASE_URL` should match your project
- `SUPABASE_KEY` should be the service role key

### Issue 2: Schema Cache Not Refreshed

After applying migrations, Supabase sometimes needs cache refresh:
1. Go to Supabase Dashboard → API Settings
2. Click "Reset" or wait a few minutes

### Issue 3: Table Created Manually (Incomplete)

If the table was created manually instead of via migration 002, it might be missing columns. Solution:

```sql
-- Drop and recreate (WARNING: DELETES ALL DATA)
DROP TABLE IF EXISTS clients CASCADE;

-- Then apply migration 002 from scratch
```

---

## Quick Fix Script

If you just want to ensure all required columns exist:

```sql
-- Add any missing columns
ALTER TABLE clients ADD COLUMN IF NOT EXISTS contact_email TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS website_type TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS builder_space_tier TEXT DEFAULT 'entry';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending_provisioning';

-- Update any NULL values
UPDATE clients SET contact_email = '' WHERE contact_email IS NULL;
UPDATE clients SET website_type = 'marketing' WHERE website_type IS NULL;
UPDATE clients SET status = 'pending_provisioning' WHERE status IS NULL;

-- Make required columns NOT NULL
ALTER TABLE clients ALTER COLUMN contact_email SET NOT NULL;
ALTER TABLE clients ALTER COLUMN website_type SET NOT NULL;
ALTER TABLE clients ALTER COLUMN status SET NOT NULL;
```

---

## After Fixing

Once the schema is correct, the form should work. Test by:

1. Ask DARX to generate onboarding link
2. Fill out form with "Shared Space" selected
3. Submit
4. Should succeed without "column not found" error
