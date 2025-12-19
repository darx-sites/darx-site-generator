# Entry-Tier Onboarding Fixes Summary

## Issues Fixed

### 1. ✅ Token Expiration (Commit: 25777a4)
**Problem**: DARX-generated onboarding links expired immediately due to in-memory token storage.

**Root Cause**: Tokens stored in `onboarding_tokens = {}` dictionary were lost on Cloud Run container restarts.

**Solution**: Migrated to persistent Supabase storage.
- Created `onboarding_tokens` table with 24-hour expiry
- Updated `generate_onboarding_token()` to persist in database
- Updated `validate_token()` to fetch from database

**Files Changed**:
- `onboarding/form.py`: Token generation/validation functions
- `supabase_migrations/004_add_onboarding_tokens.sql`: Database table

---

### 2. ✅ Builder.io Credentials Required for Entry Tier (Commit: 3529795)
**Problem**: Form validation required Builder.io API keys even when "Shared Space" was selected.

**Root Cause**: Validation didn't check tier before requiring credentials.

**Solution**: Made Builder.io credentials optional for entry-tier clients.
- Added `tier` field to form data
- Updated `validate_onboarding_form()` to conditionally require credentials
- Modified Pub/Sub message to exclude `builder` object for entry tier
- Updated Supabase record to only store credentials for premium+ tiers

**Files Changed**:
- `onboarding/form.py`: Added tier field, conditional Pub/Sub message
- `onboarding/validation.py`: Tier-based validation logic

---

## Deployment Status

### ✅ Deployed Services
- **darx-site-generator**: Revision `00108-bhf` (deployed 2025-12-16)
- **darx-provisioner**: Revision `00021-v6h` (deployed earlier)

### ⚠️ Pending: Database Migration

You still need to apply the migration for token persistence:

```bash
# File: supabase_migrations/004_add_onboarding_tokens.sql
```

**How to Apply**:
1. Go to Supabase Dashboard → SQL Editor
2. Copy contents of `004_add_onboarding_tokens.sql`
3. Run the SQL
4. Verify table exists: `SELECT * FROM onboarding_tokens LIMIT 1;`

---

## Testing Checklist

### Entry-Tier Client (Shared Space)
- [ ] Ask DARX to generate onboarding link
- [ ] Link works immediately
- [ ] Link still works after 5+ minutes
- [ ] Form shows "Shared Space" and "Individual Space" radio buttons
- [ ] "Shared Space" selected by default
- [ ] Builder.io credential fields are hidden
- [ ] Form submits successfully WITHOUT Builder.io credentials
- [ ] Pub/Sub message includes `tier: 'entry'` but NO `builder` object
- [ ] Provisioner fetches shared space credentials automatically
- [ ] Client provisions with `builder_space_mode='SHARED'`

### Premium-Tier Client (Individual Space)
- [ ] Ask DARX to generate onboarding link
- [ ] Select "Individual Space" radio button
- [ ] Builder.io credential fields appear
- [ ] Form validation requires API keys
- [ ] Form submits successfully WITH Builder.io credentials
- [ ] Pub/Sub message includes both `tier: 'premium'` AND `builder` object
- [ ] Provisioner uses provided credentials
- [ ] Client provisions with `builder_space_mode='DEDICATED'`

---

## How Entry-Tier Flow Works Now

### 1. User Requests Onboarding
DARX generates link: `https://darx-site-generator-474964350921.us-central1.run.app/onboard/{token}`

### 2. User Opens Link
- Token validated from Supabase (survives restarts)
- Form displays with "Shared Space" selected by default
- Builder.io fields hidden

### 3. User Submits Form
Form data includes:
```json
{
  "client_name": "Acme Corp",
  "client_slug": "acme-corp",
  "contact_email": "admin@acme.com",
  "website_type": "marketing",
  "tier": "entry",
  "industry": "Technology"
}
```

**Note**: NO `builder_public_key` or `builder_private_key` fields!

### 4. Pub/Sub Message Published
```json
{
  "clientId": "uuid-...",
  "clientSlug": "acme-corp",
  "clientName": "Acme Corp",
  "contactEmail": "admin@acme.com",
  "websiteType": "marketing",
  "tier": "entry",
  "metadata": {...}
}
```

**Note**: NO `builder` object!

### 5. Provisioner Receives Message
```python
# main.py line 92-99
client_tier = client_data.get('tier', 'entry')

if client_tier == 'entry':
    # Fetch shared Builder.io space from database
    builder_space = get_shared_builder_space(tier='entry')
    space_mode = 'SHARED'

    builder_public_key = builder_space['public_key']  # 81bb9692c7c64667bc07f6c29fe26109
    builder_private_key = builder_space['private_key']  # bpk-bfb39a17c9554d8181d705bb4c32fd3d
else:
    # Premium tier - use provided credentials
    space_mode = 'DEDICATED'
    builder_public_key = client_data['builder']['publicKey']
    builder_private_key = client_data['builder']['privateKey']
```

### 6. Client Provisioned
- Vercel project created
- Custom domain added: `acme-corp.darx.site`
- Environment variables set:
  ```env
  BUILDER_SPACE_MODE=SHARED
  NEXT_PUBLIC_BUILDER_API_KEY=81bb9692c7c64667bc07f6c29fe26109
  ```
- Supabase record created with `builder_space_mode='SHARED'`

---

## DARX Knowledge

**Question**: Does DARX know which keys to use when Shared Space is chosen?

**Answer**: Yes! Here's how:

1. **DARX doesn't generate API keys** - The shared space credentials are already stored in Supabase:
   ```sql
   SELECT * FROM builderio_shared_spaces WHERE tier = 'entry';
   -- Returns: public_key, private_key, space_name
   ```

2. **Provisioner fetches automatically**:
   ```python
   # intake_helpers.py
   def get_shared_builder_space(tier='entry'):
       """Retrieve shared Builder.io space credentials"""
       supabase = get_supabase_client()
       result = supabase.table('builderio_shared_spaces')
           .select('*')
           .eq('tier', tier)
           .eq('status', 'active')
           .single()
           .execute()

       # Returns: public_key, private_key, space_id, space_name
   ```

3. **DARX just needs to know the tier** - When DARX sees `tier: 'entry'` in the Pub/Sub message, it automatically fetches the shared space credentials from Supabase.

**Entry-Tier Message** (no builder object):
```json
{
  "tier": "entry",
  "clientSlug": "acme-corp",
  ...
}
```

**Premium-Tier Message** (includes builder object):
```json
{
  "tier": "premium",
  "clientSlug": "premium-corp",
  "builder": {
    "publicKey": "abc123...",
    "privateKey": "bpk-xyz..."
  }
}
```

---

## Remaining Work

1. **Apply Database Migration** (Required for token persistence)
   - File: `supabase_migrations/004_add_onboarding_tokens.sql`
   - Apply via Supabase SQL Editor

2. **Test Complete Flow**
   - Generate link with DARX
   - Submit form with "Shared Space" selected
   - Verify provisioning completes
   - Check client site at `{slug}.darx.site`

---

## Rollback if Needed

If issues arise, revert site-generator:

```bash
gcloud run services update-traffic darx-site-generator \
  --to-revisions=darx-site-generator-00106-9p2=100 \
  --region=us-central1 \
  --project=sylvan-journey-474401-f9
```

Previous revision: `00106-9p2` (before these fixes)
