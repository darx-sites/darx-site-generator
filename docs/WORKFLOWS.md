# DARX Workflows - Step-by-Step Guides

**Last Updated:** 2025-12-19
**Purpose:** Detailed workflows for common DARX operations

---

## Table of Contents

1. [Onboarding a New Client](#1-onboarding-a-new-client)
2. [Deleting a Client Site](#2-deleting-a-client-site)
3. [Recovering a Deleted Site](#3-recovering-a-deleted-site)
4. [Health Monitoring](#4-health-monitoring)
5. [Finding Orphaned Resources](#5-finding-orphaned-resources)
6. [Rollback Deployment](#6-rollback-deployment)

---

## 1. Onboarding a New Client

### User Request Examples
- "Add a new client called Acme Corp"
- "Onboard a client"
- "Create a site for XYZ Company"

### Prerequisites
- Client name
- Contact email
- Website type (marketing, ecommerce, etc.)
- Service tier (entry, standard, premium)

### Workflow

#### Step 1: Gather Information
```
DARX: "I'll help you onboard a new client. I need:
1. Client name (e.g., 'Acme Corporation')
2. Contact email
3. Website type (marketing, ecommerce, portfolio, etc.)
4. Service tier (entry, standard, premium)"
```

#### Step 2: Create Client Record
```python
Tool: start_client_onboarding
Parameters:
{
    "client_name": "Acme Corporation",
    "contact_email": "contact@acme.com",
    "website_type": "marketing",
    "tier": "standard"
}
```

**What happens:**
- Creates record in Supabase `clients` table
- Generates client_slug (e.g., 'acme-corporation')
- Sets status = 'pending_provisioning'
- Returns client_id

#### Step 3: Inform User
```
DARX: "Created client record for Acme Corporation (slug: acme-corporation).
Status: Pending Provisioning.

Ready to proceed with provisioning? This will:
- Generate Next.js site code
- Create GitHub repository
- Set up Vercel deployment
- Configure Builder.io CMS
- Create backups in GCS"
```

#### Step 4: Trigger Provisioning (After Confirmation)
```python
Tool: trigger_client_provisioning
Parameters:
{
    "client_slug": "acme-corporation"
}
```

**What happens:**
- Publishes message to Pub/Sub topic 'darx-client-onboarding'
- darx-provisioner service receives message
- Automated provisioning begins

#### Step 5: Monitor Progress
```python
# Option 1: Query Supabase for status
Tool: query_supabase
Parameters:
{
    "operation": "select",
    "table": "clients",
    "filters": {"client_slug": "acme-corporation"},
    "columns": ["status", "github_repo", "vercel_project_id"]
}

# Option 2: Get comprehensive details
Tool: get_site_details
Parameters:
{
    "client_slug": "acme-corporation"
}
```

#### Step 6: Verify Completion
```
DARX: "Provisioning complete for Acme Corporation!

✅ GitHub: github.com/darx-sites/acme-corporation
✅ Vercel: https://acme-corporation.vercel.app
✅ Builder.io: Space configured
✅ Status: Active

The site is live and ready for content editing."
```

### Troubleshooting

**Provisioning Failed:**
1. Check `registry_operations_log` for error details
2. Check provisioner logs in Cloud Logging
3. Verify platform credentials in Secret Manager
4. Retry provisioning if safe to do so

**Already Exists:**
- Check if client_slug conflicts with existing site
- Suggest alternative slug

---

## 2. Deleting a Client Site

### User Request Examples
- "Delete acme-corp"
- "Remove the site for Acme"
- "Deactivate acme-corp"

### CRITICAL SAFETY CHECKS
1. ✅ Always confirm with user BEFORE deletion
2. ✅ Explain this is soft delete (30-day recovery)
3. ✅ Require deletion reason for audit
4. ✅ Verify user has authority to delete

### Workflow

#### Step 1: Verify Site Exists
```python
Tool: get_site_details
Parameters:
{
    "client_slug": "acme-corp"
}
```

**Check response:**
- Site exists?
- Current status?
- Any active deployments?

#### Step 2: Confirm with User
```
DARX: "I found the site for acme-corp:
- Status: active
- GitHub: github.com/darx-sites/acme-corp
- Vercel: https://acme-corp.vercel.app
- Last deployment: 2 days ago

⚠️ IMPORTANT: This will perform a SOFT DELETE with 30-day recovery window:
- GitHub repo will be archived (renamed to ARCHIVED-acme-corp)
- Vercel project will be paused
- Builder.io content will be archived
- Backups will be retained for 30 days

You can recover this site within 30 days using the recover command.

Please confirm:
1. Reason for deletion (required for audit): ___
2. Type 'CONFIRM DELETE' to proceed"
```

#### Step 3: Execute Soft Delete (After Confirmation)
```python
Tool: delete_site
Parameters:
{
    "client_slug": "acme-corp",
    "deleted_by": "user@email.com",  # Extract from Slack user
    "reason": "Client contract ended",  # From user confirmation
    "confirm": true
}
```

**What happens:**
1. Creates snapshot in `deleted_sites` table
2. Archives GitHub repo (renamed to ARCHIVED-acme-corp, made private)
3. Marks Vercel project for deletion (doesn't delete yet)
4. Archives Builder.io content with timestamp
5. Tags GCS backups for 30-day retention
6. Updates `clients.status` = 'deleted'
7. Sets `recovery_deadline` = now() + 30 days
8. Logs operation in `registry_operations_log`

#### Step 4: Verify Deletion
```python
Tool: list_darx_sites
Parameters:
{
    "status": "deleted",
    "limit": 10
}
```

#### Step 5: Inform User
```
DARX: "Site acme-corp successfully deleted (soft delete).

Platform Results:
✅ GitHub: Archived as ARCHIVED-acme-corp
✅ Vercel: Marked for deletion
✅ Builder.io: Content archived
✅ GCS: Backups retained

Recovery Deadline: 2026-01-18 (30 days from now)

To recover this site, use: recover acme-corp
After 30 days, the site will be permanently deleted."
```

### Troubleshooting

**Platform Failures:**
- If GitHub archival fails: Site remains active, deletion not completed
- If Vercel marking fails: Manual intervention may be needed
- Check `deleted_sites` table for platform-specific results

**Accidental Deletion:**
- Immediately use recover workflow if within 30 days
- After 30 days: Site is permanently deleted, no recovery possible

---

## 3. Recovering a Deleted Site

### User Request Examples
- "Recover acme-corp"
- "Restore the deleted site for Acme"
- "Undo deletion of acme-corp"

### Prerequisites
- Site was soft-deleted (not permanently deleted)
- Within 30-day recovery window
- Platform resources still exist

### Workflow

#### Step 1: Verify Deleted Site Exists
```python
Tool: list_darx_sites
Parameters:
{
    "status": "deleted"
}
```

**Check for site in results:**
- Is it in the deleted list?
- Has it been recovered already?
- Is recovery_deadline passed?

#### Step 2: Check Recovery Deadline
```python
Tool: query_supabase
Parameters:
{
    "operation": "select",
    "table": "deleted_sites",
    "filters": {"client_data->>client_slug": "acme-corp"},
    "columns": ["recovery_deadline", "recovered", "deleted_at"]
}
```

**Verify:**
- `recovery_deadline` > now()
- `recovered` = false

#### Step 3: Inform User & Confirm
```
DARX: "Found deleted site: acme-corp
- Deleted: 5 days ago
- Recovery deadline: 25 days remaining
- Platforms: GitHub, Vercel, Builder.io, GCS

Recovery will:
✅ Restore GitHub repo (rename back, make public)
✅ Re-enable Vercel deployments
✅ Restore Builder.io content
✅ Remove GCS backup deletion tags
✅ Create new client record in Supabase

Proceed with recovery?"
```

#### Step 4: Execute Recovery (After Confirmation)
```python
Tool: recover_deleted_site
Parameters:
{
    "client_slug": "acme-corp",
    "recovered_by": "user@email.com"
}
```

**What happens:**
1. Fetches deleted_sites record
2. Verifies recovery window
3. Restores GitHub repo (rename, make public)
4. Re-enables Vercel deployments
5. Restores Builder.io content
6. Removes GCS deletion tags
7. Creates NEW client record (new UUID)
8. Marks `deleted_sites.recovered` = true

#### Step 5: Verify Recovery
```python
Tool: get_site_details
Parameters:
{
    "client_slug": "acme-corp"
}
```

**Check:**
- Status = 'active'
- GitHub repo exists and is public
- Vercel project is live
- Health status

#### Step 6: Inform User
```
DARX: "Site acme-corp successfully recovered!

✅ GitHub: Restored to github.com/darx-sites/acme-corp
✅ Vercel: Live at https://acme-corp.vercel.app
✅ Builder.io: Content restored
✅ GCS: Backups preserved
✅ Status: Active

New Client ID: {new_uuid}
Site is fully operational."
```

### Troubleshooting

**Recovery Deadline Passed:**
```
DARX: "❌ Cannot recover acme-corp: Recovery deadline has passed.
The site was permanently deleted after the 30-day window.

To recreate this site, you'll need to start a new onboarding."
```

**Platform Resources Missing:**
- If GitHub repo was manually deleted: Cannot recover
- If Vercel project was deleted: Cannot recover
- May need partial recovery or full re-provisioning

---

## 4. Health Monitoring

### User Request Examples
- "Is acme-corp healthy?"
- "Check the health of all sites"
- "What sites are down?"

### Workflow

#### Option A: Check Single Site (Cached)
```python
Tool: get_site_health
Parameters:
{
    "client_slug": "acme-corp"
}
```

**Returns:**
- Latest health check from `site_health_checks` table
- Fast, doesn't trigger new check

#### Option B: Check Single Site (Real-Time)
```python
Tool: check_site_health
Parameters:
{
    "client_slug": "acme-corp"
}
```

**What happens:**
1. Checks GitHub repo (exists, recent commits)
2. Checks Vercel (deployment status, SSL)
3. Checks Builder.io (space accessible)
4. Checks GCS (backups exist)
5. Checks Staging URL (HTTP 200 response)
6. Aggregates to overall status
7. Stores in `site_health_checks` table
8. Updates `clients.health_status`

#### Option C: List Unhealthy Sites
```python
Tool: list_darx_sites
Parameters:
{
    "health_status": "degraded"  # or "down"
}
```

#### Health Status Interpretation

**healthy:**
- All platforms operational
- No issues detected
- Site fully functional

**degraded:**
- Some platforms have issues
- Site mostly functional
- Example: GitHub repo exists but no recent commits

**down:**
- Critical platforms failing
- Site not functional
- Example: Vercel deployment failed, URL not accessible

**unknown:**
- Never been health checked
- New site
- Health monitoring not yet configured

### Reporting to User

```
DARX: "Health Status for acme-corp:

Overall: ✅ Healthy

Platform Details:
✅ GitHub: Repo accessible, last commit 2 hours ago
✅ Vercel: Deployment successful, SSL valid
✅ Builder.io: Space accessible, 15 content items
✅ GCS: 5 backups available, latest: 1 day ago
✅ Staging URL: Responding (200 OK)

Last checked: 5 minutes ago"
```

---

## 5. Finding Orphaned Resources

### Purpose
Identify platform resources that exist but have no corresponding client in Supabase

### Workflow

#### Step 1: Trigger Inventory Sync (Admin Only)
```python
# This would be a future tool
# For now, check platform_inventory table directly
Tool: query_supabase
Parameters:
{
    "operation": "select",
    "table": "platform_inventory",
    "filters": {"is_orphaned": true}
}
```

#### Step 2: Review Orphaned Resources
```python
Tool: query_supabase
Parameters:
{
    "operation": "select",
    "table": "v_orphaned_resources",
    "columns": ["platform", "resource_name", "resource_url", "last_verified_at"]
}
```

**Results:**
```
Orphaned Resources Found:
1. GitHub: darx-sites/test-client-old (no matching client)
2. Vercel: abandoned-project (no matching client)
3. GCS: projects/legacy-site/ (no matching client)
```

#### Step 3: Investigate Each Resource
1. Check if this is a legitimate site
2. Check if client was deleted (check `deleted_sites`)
3. Determine if resource should be cleaned up or linked

#### Step 4: Clean Up (If Appropriate)
```
For each orphaned resource:
- GitHub: Delete repo or archive
- Vercel: Delete project
- Builder.io: Delete space
- GCS: Delete backups
```

---

## 6. Rollback Deployment

### User Request Examples
- "Rollback acme-corp to previous version"
- "Undo the latest deployment"
- "Go back to the last working version"

### Prerequisites
- Site has deployment history in `site_deployments` table
- Previous deployment commit SHA available
- GitHub repo still exists

### Workflow

#### Step 1: Get Deployment History
```python
Tool: get_site_details
Parameters:
{
    "client_slug": "acme-corp"
}
```

**Review deployments array:**
```json
"deployments": [
    {
        "deployed_at": "2025-12-19T10:00:00Z",
        "commit_sha": "abc123",
        "status": "success"
    },
    {
        "deployed_at": "2025-12-18T15:30:00Z",
        "commit_sha": "def456",
        "status": "success"
    }
]
```

#### Step 2: Identify Target Version
```
DARX: "Found 10 deployments for acme-corp:

Latest: abc123 (Dec 19, 10:00 AM) - Current
Previous: def456 (Dec 18, 3:30 PM) - Last good version

Which version would you like to rollback to?"
```

#### Step 3: Revert GitHub Commit
```python
# Use GitHub tool to revert
Tool: access_github
Parameters:
{
    "operation": "revert_commit",
    "repo": "darx-sites/acme-corp",
    "commit_sha": "abc123",  # Commit to revert
    "target_branch": "main"
}
```

**What happens:**
1. Creates revert commit in GitHub
2. Vercel detects push to main
3. Vercel auto-deploys reverted code
4. Site returns to previous state

#### Step 4: Verify Rollback
```python
Tool: check_site_health
Parameters:
{
    "client_slug": "acme-corp"
}
```

#### Step 5: Log Rollback
```python
Tool: query_supabase
Parameters:
{
    "operation": "insert",
    "table": "site_deployments",
    "data": {
        "client_id": "{uuid}",
        "commit_sha": "def456",  # Rolled back to
        "deployed_by": "darx-rollback",
        "deployment_type": "rollback",
        "status": "success"
    }
}
```

### Alternative: Manual Rollback via Vercel

```
DARX: "Alternatively, you can rollback via Vercel dashboard:
1. Visit https://vercel.com/darx/acme-corp/deployments
2. Find the deployment you want to rollback to
3. Click 'Promote to Production'

This is instant and doesn't require a new git commit."
```

---

**End of Workflows**
