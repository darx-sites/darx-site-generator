# Onboarding Token Persistence Fix

## Problem

DARX was generating onboarding links that immediately expired because tokens were stored in-memory (`onboarding_tokens = {}`). When Cloud Run restarts the container (cold starts), all tokens are lost.

## Solution

Moved token storage from in-memory to **persistent Supabase storage**.

---

## Deployment Steps

### 1. Apply Database Migration

Execute the SQL migration in Supabase SQL editor:

```bash
# File: supabase_migrations/004_add_onboarding_tokens.sql
```

Or via Supabase dashboard:
1. Go to https://supabase.com/dashboard
2. Select your project
3. Navigate to **SQL Editor**
4. Copy the contents of `supabase_migrations/004_add_onboarding_tokens.sql`
5. Click **Run**

This creates:
- `onboarding_tokens` table with columns: `token`, `client_slug`, `created_at`, `expires_at`, `used`
- Indexes for efficient lookups
- Cleanup function for expired tokens

### 2. Deploy Updated Site Generator

```bash
cd /Users/marvinromero/darx-site-generator

gcloud run deploy darx-site-generator \
  --source . \
  --platform managed \
  --region us-central1 \
  --project sylvan-journey-474401-f9 \
  --allow-unauthenticated \
  --clear-base-image \
  --timeout=20m
```

### 3. Verify Deployment

Ask DARX to generate a new onboarding link:

**Example Prompt**:
> "Generate an onboarding link for test-client-123"

DARX should return a link like:
```
https://darx-site-generator-474964350921.us-central1.run.app/onboard/abc123...
```

**Test the Link**:
1. Copy the link
2. Wait 5 minutes (to simulate Cloud Run restart)
3. Visit the link
4. **Expected**: Form should load successfully (not show "expired" error)

---

## What Changed

### Before (In-Memory Storage)
```python
# ❌ Problem: Tokens lost on container restart
onboarding_tokens = {}

def generate_onboarding_token(client_slug: str) -> str:
    token = secrets.token_urlsafe(32)
    onboarding_tokens[token] = {
        'client_slug': client_slug,
        'created_at': datetime.utcnow(),
        'used': False
    }
    return token
```

### After (Supabase Persistence)
```python
# ✅ Solution: Tokens persisted in database
def generate_onboarding_token(client_slug: str) -> str:
    token = secrets.token_urlsafe(32)

    supabase = get_supabase()
    supabase.table('onboarding_tokens').insert({
        'token': token,
        'client_slug': client_slug,
        'created_at': datetime.utcnow().isoformat(),
        'used': False,
        'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }).execute()

    return token
```

---

## Benefits

1. **Tokens survive Cloud Run restarts** - No more "expired link" errors
2. **24-hour expiry still enforced** - Security maintained via `expires_at` column
3. **One-time use guaranteed** - `used` flag prevents reuse
4. **Automatic cleanup** - SQL function removes expired tokens

---

## Testing Checklist

- [ ] Database migration applied successfully
- [ ] Site-generator redeployed with new code
- [ ] DARX can generate onboarding links
- [ ] Links work immediately after generation
- [ ] Links still work after 5-10 minutes (Cloud Run restart simulation)
- [ ] Links expire after 24 hours
- [ ] Used links cannot be reused
- [ ] Supabase table `onboarding_tokens` has entries

---

## Monitoring

Check Supabase table for tokens:

```sql
-- View all active tokens
SELECT
    token,
    client_slug,
    created_at,
    expires_at,
    used,
    EXTRACT(EPOCH FROM (expires_at - NOW())) / 3600 AS hours_until_expiry
FROM onboarding_tokens
WHERE used = false
  AND expires_at > NOW()
ORDER BY created_at DESC;

-- Count token status
SELECT
    CASE
        WHEN used THEN 'used'
        WHEN expires_at < NOW() THEN 'expired'
        ELSE 'active'
    END AS status,
    COUNT(*) AS count
FROM onboarding_tokens
GROUP BY status;
```

---

## Rollback

If issues arise, revert to previous revision:

```bash
# Find previous revision
gcloud run revisions list \
  --service=darx-site-generator \
  --region=us-central1 \
  --project=sylvan-journey-474401-f9 \
  --limit=5

# Revert to specific revision
gcloud run services update-traffic darx-site-generator \
  --to-revisions=darx-site-generator-00106-9p2=100 \
  --region=us-central1 \
  --project=sylvan-journey-474401-f9
```

---

## Next Steps After Deployment

1. Test with DARX: "Generate onboarding link for test-entry-client"
2. Wait 5 minutes (simulate restart)
3. Visit link and verify form loads
4. Complete onboarding flow with "Shared Space" selected
5. Verify client provisions successfully without Builder.io credentials
