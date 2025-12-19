# Verify Form Submission for test-client-2

## Check if Record Exists

Run this in Supabase SQL Editor:

```sql
-- Find test-client-2
SELECT
    id,
    client_name,
    client_slug,
    contact_email,
    website_type,
    builder_space_tier,
    status,
    created_at,
    builder_public_key,
    builder_private_key
FROM clients
WHERE client_slug = 'test-client-2';
```

**Expected**: Should return 1 row with the submission data

---

## Check All Recent Submissions

```sql
-- Show all clients created in last hour
SELECT
    id,
    client_name,
    client_slug,
    contact_email,
    builder_space_tier,
    status,
    created_at
FROM clients
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
```

---

## Issue: DARX Can't See the Record

### Possible Causes

1. **DARX is querying wrong table**
   - DARX might be looking at `client_onboarding` table instead of `clients`

2. **DARX doesn't have access to `clients` table**
   - Check RLS (Row Level Security) policies

3. **Pub/Sub message not published**
   - Check if DARX is waiting for Pub/Sub notification
   - Form inserts into DB but doesn't trigger DARX

---

## Solution: Check Pub/Sub Topic

The form should publish a message to trigger provisioning. Check Cloud Pub/Sub:

```bash
# List recent messages (if available)
gcloud pubsub topics list --project=sylvan-journey-474401-f9

# Check if topic exists
gcloud pubsub topics describe darx-client-onboarding \
  --project=sylvan-journey-474401-f9
```

---

## How DARX Should See New Clients

DARX has two ways to see new client submissions:

### Method 1: Direct Database Query (Recommended)
DARX queries `clients` table directly:

```sql
SELECT * FROM clients
WHERE client_slug = 'test-client-2';
```

**Problem**: If DARX is using wrong table name or doesn't have permissions

### Method 2: Pub/Sub Notification (Current)
Form publishes message → DARX receives → DARX processes

**Problem**: If Pub/Sub publishing failed silently

---

## Debug: Check Cloud Run Logs

Check site-generator logs for Pub/Sub errors:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=darx-site-generator" \
  --limit 50 \
  --project sylvan-journey-474401-f9 \
  --format json \
  | grep -i "pub\|test-client-2\|error"
```

---

## Immediate Fix

If the record exists in `clients` table but DARX can't see it:

1. **Tell DARX the exact table to query**:
   > "Check the clients table in Supabase for test-client-2"

2. **Give DARX the client ID directly**:
   ```sql
   SELECT id FROM clients WHERE client_slug = 'test-client-2';
   ```
   > "The client ID for test-client-2 is: [paste ID here]"

3. **Manually trigger provisioning** (if Pub/Sub failed):
   - Get the client_id from query above
   - Publish Pub/Sub message manually:

   ```bash
   gcloud pubsub topics publish darx-client-onboarding \
     --project=sylvan-journey-474401-f9 \
     --message='{
       "clientId": "UUID-FROM-QUERY",
       "clientSlug": "test-client-2",
       "clientName": "Test Client 2",
       "tier": "entry",
       "websiteType": "marketing"
     }'
   ```

---

## Long-term Fix

Update DARX's tool to query the `clients` table directly instead of relying only on Pub/Sub notifications.

DARX should have a tool like:

```python
def get_client_by_slug(client_slug: str):
    """Query clients table for a specific client"""
    supabase = get_supabase_client()
    result = supabase.table('clients')\
        .select('*')\
        .eq('client_slug', client_slug)\
        .single()\
        .execute()
    return result.data
```

Then DARX can directly look up any client without waiting for Pub/Sub.
