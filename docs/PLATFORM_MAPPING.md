# DARX Platform Mapping - Where Things Live

**Last Updated:** 2025-12-19
**Purpose:** Guide for DARX to understand where client data and resources are stored across all platforms

---

## Quick Reference: Where to Find What

| Data Type | Platform | Location | Why There | Access Method |
|-----------|----------|----------|-----------|---------------|
| **Client Metadata** | Supabase | `clients` table | Structured relational data | Supabase client |
| **Site Status** | Supabase | `clients.status` | Operational state tracking | Supabase client |
| **Health Status** | Supabase | `site_health_checks` table | Historical health tracking | Supabase client |
| **Deployment History** | Supabase | `site_deployments` table | Audit trail | Supabase client |
| **Deleted Sites** | Supabase | `deleted_sites` table | 30-day recovery window | Supabase client |
| **Platform Inventory** | Supabase | `platform_inventory` table | Multiplatform resource tracking | Supabase client |
| **Credentials** | GCP Secret Manager | `client-{slug}-builder-*-key` | Encrypted, access-controlled | Secret Manager API |
| **Generated Code** | GitHub | `darx-sites/{slug}` | Version control, Vercel integration | GitHub API |
| **Live Sites** | Vercel | Project `{slug}` | Production deployments | Vercel API |
| **Site URLs** | Vercel | `https://{slug}.vercel.app` | Public access | HTTP |
| **Visual Content** | Builder.io | Spaces (shared or dedicated) | CMS content management | Builder.io API |
| **Code Backups** | GCS | `gs://darx-generated-sites/projects/{slug}/` | Disaster recovery | GCS client |
| **Audit Logs** | Supabase | `registry_operations_log` table | Operation tracking | Supabase client |

---

## Detailed Platform Breakdown

### 1. Supabase - Central Database

**Database:** `darx-db` (PostgreSQL)
**Purpose:** Central source of truth for all client metadata and operational data

#### Core Tables

**`clients` table** - Client metadata and configuration
```
Stores: Names, slugs, status, tier, contact info, timestamps
Primary Key: id (UUID)
Unique Key: client_slug (e.g., 'acme-corp')
Why: Structured relational data, easy querying
Access: get_supabase_client() from darx.clients.supabase
```

Key columns:
- `id` (UUID) - Primary key
- `client_slug` (TEXT, UNIQUE) - Human-readable identifier
- `client_name` (TEXT) - Display name
- `status` (TEXT) - Current state: 'pending_provisioning', 'active', 'deleted'
- `health_status` (TEXT) - Overall health: 'healthy', 'degraded', 'down', 'unknown'
- `contact_email` (TEXT) - Primary contact
- `subscription_tier` (TEXT) - Service tier
- `github_repo` (TEXT) - Full repo name (e.g., 'darx-sites/acme-corp')
- `vercel_project_id` (TEXT) - Vercel project identifier
- `builder_space_id` (TEXT) - Builder.io space ID
- `builder_space_tier` (TEXT) - 'shared' or 'dedicated'
- `deletion_scheduled_at` (TIMESTAMP) - When soft delete initiated
- `created_at`, `updated_at` (TIMESTAMP) - Audit timestamps

**`site_deployments` table** - Deployment history
```
Stores: Every deployment with commit SHA, Vercel deployment ID, status
Foreign Key: client_id → clients.id
Why: Enables rollback capability, maintains history
Access: Supabase client
```

**`deleted_sites` table** - Soft delete with recovery (CRITICAL)
```
Stores: Complete snapshot of client data before deletion
Recovery Window: 30 days (auto-set by trigger)
Platform Tracking: github_deleted, vercel_deleted, builder_deleted, gcs_deleted
Why: Enables safe deletion with recovery mechanism
Access: Supabase client
```

Key columns:
- `id` (UUID) - Primary key
- `original_client_id` (UUID) - Reference to original client
- `client_data` (JSONB) - Complete snapshot
- `deleted_by` (TEXT) - Who initiated deletion
- `deletion_reason` (TEXT) - Audit reason
- `deleted_at` (TIMESTAMP) - When deleted
- `recovery_deadline` (TIMESTAMP) - Auto-set to now() + 30 days
- `recovered` (BOOLEAN) - Whether site was recovered
- `recovered_at` (TIMESTAMP) - When recovered
- `recovered_by` (TEXT) - Who recovered

**`site_health_checks` table** - Automated monitoring
```
Stores: Health check results across all platforms
Foreign Key: client_id → clients.id
Why: Historical health tracking, trend analysis
Access: Supabase client
```

Platform health fields:
- `overall_status` (TEXT) - 'healthy', 'degraded', 'down'
- `github_healthy` (BOOLEAN) - Repo accessible
- `vercel_healthy` (BOOLEAN) - Deployment successful
- `builder_healthy` (BOOLEAN) - Space accessible
- `gcs_healthy` (BOOLEAN) - Backups exist
- `staging_url_accessible` (BOOLEAN) - URL responds

**`platform_inventory` table** - Multiplatform resource tracking
```
Stores: Complete inventory of all resources across platforms
Detects: Orphaned resources (exists in platform but no client)
Detects: Drift (in DB but not in platform)
Why: Multiplatform awareness, resource cleanup
Access: Supabase client
```

Key columns:
- `platform` (TEXT) - 'github', 'vercel', 'builderio', 'gcs'
- `resource_type` (TEXT) - 'repository', 'project', 'space', 'backup'
- `resource_id` (TEXT) - Platform-specific identifier
- `resource_name` (TEXT) - Human-readable name
- `client_id` (UUID, NULLABLE) - Links to client if not orphaned
- `is_orphaned` (BOOLEAN) - True if no matching client
- `last_verified_at` (TIMESTAMP) - Last inventory sync

**`registry_operations_log` table** - Complete audit trail
```
Stores: Every site operation (create, update, delete, recover)
Tracks: Platform-specific results, success/failure counts
Why: Debugging, compliance, rollback tracking
Access: Supabase client
```

#### Views for Easy Querying

**`v_client_full_inventory`** - One query to see everything
```
Joins: clients + platform_inventory + latest deployment + health
Returns: Complete site view across all platforms
Use: Primary view for DARX to query site details
```

**`v_orphaned_resources`** - Resources needing cleanup
```
Filters: platform_inventory WHERE is_orphaned = true
Sorted by: discovery date
Use: Finding resources to clean up
```

**`v_sites_pending_deletion`** - Soft-deleted sites
```
Source: deleted_sites WHERE recovered = false
Shows: Days until permanent deletion, platform deletion status
Use: Recovery window tracking
```

---

### 2. GCP Secret Manager - Sensitive Credentials

**Project:** `sylvan-journey-474401-f9`
**Purpose:** Encrypted storage for API keys and secrets

#### Secret Naming Patterns

**Builder.io Public Keys**
```
Pattern: client-{slug}-builder-public-key
Example: client-acme-corp-builder-public-key
Stores: Builder.io public API key
Why: Needed for Builder.io API calls
Access: get_secret_manager_client()
```

**Builder.io Private Keys**
```
Pattern: client-{slug}-builder-private-key
Example: client-acme-corp-builder-private-key
Stores: Builder.io private API key (admin access)
Why: Space creation, content management
Access: get_secret_manager_client()
```

**Space IDs**
```
Pattern: client-{slug}-builder-space-id
Example: client-acme-corp-builder-space-id
Stores: Builder.io space identifier
Why: Scoping content queries
Access: get_secret_manager_client()
```

#### Why Secret Manager?
- ✅ Encrypted at rest and in transit
- ✅ IAM-based access control
- ✅ Audit logs for access
- ✅ Automatic rotation support
- ✅ Versioning (can rollback)

---

### 3. GitHub - Version-Controlled Code

**Organization:** `darx-sites`
**Purpose:** Version control for generated Next.js code, enables Vercel auto-deploy

#### Repository Naming

**Active Sites**
```
Pattern: darx-sites/{client-slug}
Example: darx-sites/acme-corp
Visibility: Public (for Vercel integration)
Default Branch: main
Why: Version control, Vercel integration, collaboration
Access: GitHub API (PyGithub)
```

**Archived Sites** (Soft Deleted)
```
Pattern: darx-sites/ARCHIVED-{client-slug}
Example: darx-sites/ARCHIVED-acme-corp
Visibility: Private
Why: Maintains code for 30-day recovery window
Access: GitHub API
```

#### Repository Contents

Standard Next.js structure:
```
/
├── pages/              # Next.js pages
├── components/         # React components
├── public/             # Static assets
├── styles/             # CSS/styling
├── builder.config.js   # Builder.io integration
├── package.json        # Dependencies
├── next.config.js      # Next.js configuration
└── vercel.json         # Vercel configuration
```

#### Why GitHub?
- ✅ Version control (can rollback deployments)
- ✅ Native Vercel integration (auto-deploy on push)
- ✅ Code review capability
- ✅ Free for public repos
- ✅ Industry standard

---

### 4. Vercel - Production Deployments

**Account:** DARX Vercel account
**Purpose:** Hosting, deployment, CDN, SSL

#### Project Naming

```
Pattern: {client-slug}
Example: acme-corp
Visibility: Public
Domain: https://{slug}.vercel.app
Why: Production hosting, auto-deploy from GitHub
Access: Vercel API
```

#### Environment Variables

Set per-project in Vercel:
```
BUILDER_PUBLIC_KEY={from Secret Manager}
BUILDER_SPACE_ID={from Secret Manager}
NEXT_PUBLIC_BUILDER_API_KEY={public key}
```

#### Deployment URLs

**Production URL**
```
Pattern: https://{client-slug}.vercel.app
Example: https://acme-corp.vercel.app
Auto-SSL: Yes (Vercel manages)
CDN: Global edge network
```

**Preview URLs** (for each commit)
```
Pattern: https://{client-slug}-{git-branch}-{team}.vercel.app
Example: https://acme-corp-feat-update-darx.vercel.app
Auto-generated: Yes (on every push)
```

#### Why Vercel?
- ✅ Zero-config Next.js deployment
- ✅ Auto-deploy from GitHub
- ✅ Global CDN
- ✅ Free SSL certificates
- ✅ Preview deployments for every commit
- ✅ Serverless functions support

---

### 5. Builder.io - Visual CMS

**Purpose:** Visual content management, no-code editing

#### Space Models

**SHARED Tier** (Entry/Standard)
```
Space: Single shared space for all clients
Space ID: darx-shared-builder-space-id
Content Filtering: client_slug field on every content item
Query: content.client_slug == 'acme-corp'
Why: Cost-effective for smaller clients
Limitation: Content mixed, requires filtering
```

**DEDICATED Tier** (Premium)
```
Space: One unique space per client
Space ID: Stored in Secret Manager
Content Isolation: True (no filtering needed)
Query: Direct space queries
Why: Data isolation, better performance
Cost: Higher (Builder.io charges per space)
```

#### Content Storage

Builder.io stores:
- Page content (visual elements, text, images)
- Component configurations
- A/B test variants
- Publish history

**NOT stored in Builder.io:**
- Site code (that's in GitHub)
- Deployment artifacts (that's in Vercel)
- Client metadata (that's in Supabase)

#### Why Builder.io?
- ✅ Visual editing (no code required)
- ✅ A/B testing built-in
- ✅ Component library
- ✅ Publish workflow
- ✅ Content scheduling
- ✅ Multi-user collaboration

---

### 6. Google Cloud Storage - Code Backups

**Bucket:** `darx-generated-sites`
**Purpose:** Disaster recovery, point-in-time restoration

#### Backup Structure

```
gs://darx-generated-sites/projects/{client-slug}/
  ├── generation-{timestamp}.zip     # Full code snapshot
  ├── generation-{timestamp}.zip
  └── latest.zip                     # Symlink to latest
```

Example:
```
gs://darx-generated-sites/projects/acme-corp/
  ├── generation-20251219-123456.zip
  ├── generation-20251218-091234.zip
  └── latest.zip → generation-20251219-123456.zip
```

#### Backup Retention

**Active Sites:**
- Keep all backups indefinitely
- No auto-deletion

**Soft-Deleted Sites:**
- Tag with `deletion_scheduled: true`
- Retain for 30 days
- Permanent delete after recovery_deadline

#### Why GCS?
- ✅ Durable (11 nines of durability)
- ✅ Versioning support
- ✅ Lifecycle policies for auto-cleanup
- ✅ Cheap storage costs
- ✅ Fast retrieval

---

## Data Flow Diagrams

### Site Creation Flow

```
User → DARX (Slack)
  ↓ start_client_onboarding
DARX → Supabase: Insert into clients table
  ↓ trigger_client_provisioning
DARX → Pub/Sub: Publish to darx-client-onboarding
  ↓
darx-provisioner (Cloud Run):
  1. Generate Next.js code
  2. Create GitHub repo → darx-sites/{slug}
  3. Create Vercel project → {slug}
  4. Create/configure Builder.io space
  5. Create GCS backup
  6. Update Supabase: status = 'active'
```

### Site Deletion Flow (Soft Delete)

```
User → DARX: "Delete acme-corp"
  ↓ delete_site
DARX → darx-site-generator: DELETE /sites/acme-corp
  ↓
darx-site-generator → darx-registry: DELETE /api/v1/sites/acme-corp
  ↓
darx-registry (MultiplatformOrchestrator):
  1. Supabase: Insert into deleted_sites (snapshot)
  2. GitHub: Rename repo to ARCHIVED-{slug}, make private
  3. Vercel: Mark for deletion (don't delete yet)
  4. Builder.io: Archive content with timestamp
  5. GCS: Tag backups for retention
  6. Supabase: Update clients.status = 'deleted'
  7. Set recovery_deadline = now() + 30 days
```

### Health Check Flow

```
User → DARX: "Check health of acme-corp"
  ↓ check_site_health
DARX → darx-site-generator: POST /sites/acme-corp/health/check
  ↓
darx-site-generator → darx-registry: POST /api/v1/sites/acme-corp/health/check
  ↓
darx-registry (MultiplatformOrchestrator):
  1. GitHub: Check repo exists, get last commit
  2. Vercel: Check deployment status, SSL validity
  3. Builder.io: Check space accessible
  4. GCS: Check backups exist
  5. HTTP: Check staging URL responds
  6. Supabase: Insert into site_health_checks
  7. Update clients.health_status
```

---

## Common Queries DARX Should Know

### "Where is the client data for acme-corp?"

```python
# Metadata and status
supabase.table('clients').select('*').eq('client_slug', 'acme-corp').execute()

# GitHub code
https://github.com/darx-sites/acme-corp

# Vercel deployment
https://acme-corp.vercel.app

# Builder.io content
# If SHARED tier:
builder_client.content('page', {'client_slug': 'acme-corp'})
# If DEDICATED tier:
space_id = get_secret('client-acme-corp-builder-space-id')
builder_client.content('page', space_id=space_id)

# GCS backups
gs://darx-generated-sites/projects/acme-corp/
```

### "Is acme-corp healthy?"

```python
# Cached health status
supabase.table('clients').select('health_status').eq('client_slug', 'acme-corp').execute()

# Latest health check details
supabase.table('site_health_checks')\
  .select('*')\
  .eq('client_id', client_id)\
  .order('checked_at', desc=True)\
  .limit(1)\
  .execute()

# Trigger new health check
darx_site_generator.post('/sites/acme-corp/health/check')
```

### "What sites are deleted?"

```python
# Soft-deleted sites (recoverable)
supabase.table('deleted_sites').select('*').eq('recovered', False).execute()

# Or use view
supabase.table('v_sites_pending_deletion').select('*').execute()

# Days until permanent deletion
# Check recovery_deadline field
```

### "What resources exist on GitHub?"

```python
# From platform_inventory
supabase.table('platform_inventory')\
  .select('*')\
  .eq('platform', 'github')\
  .eq('resource_type', 'repository')\
  .execute()

# Orphaned GitHub repos (no matching client)
supabase.table('platform_inventory')\
  .select('*')\
  .eq('platform', 'github')\
  .eq('is_orphaned', True)\
  .execute()

# Or use view
supabase.table('v_orphaned_resources')\
  .select('*')\
  .eq('platform', 'github')\
  .execute()
```

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **darx-provisioner** | Cloud Run service | Client onboarding (Pub/Sub triggered) |
| **darx-site-generator** | https://darx-site-generator-slgtfcnoxq-uc.a.run.app | Site generation & management API |
| **darx-registry** | https://darx-registry-slgtfcnoxq-uc.a.run.app | Multiplatform orchestration |
| **darx-reasoning** | https://darx-reasoning-slgtfcnoxq-uc.a.run.app | DARX brain (function calling) |
| **Supabase** | Via Supabase client | Database |
| **GitHub** | Via PyGithub API | Code repos |
| **Vercel** | Via Vercel API | Deployments |
| **Builder.io** | Via Builder.io SDK | CMS |
| **GCS** | Via google-cloud-storage | Backups |

---

## Critical Patterns DARX Must Remember

1. **Always use client_slug as the human identifier** (not client_id UUID)
2. **Soft delete creates snapshots** - data is NOT lost for 30 days
3. **Health checks have two modes**: cached (get_site_health) vs real-time (check_site_health)
4. **Platform inventory tracks ALL resources** - use it to find orphaned resources
5. **Credentials are in Secret Manager** - never in Supabase or code
6. **GitHub repos auto-deploy to Vercel** - push to main = production deploy
7. **Builder.io content is filtered by client_slug** (shared tier) or isolated by space (dedicated tier)
8. **GCS backups are point-in-time snapshots** - use for disaster recovery
9. **Views simplify queries** - prefer v_client_full_inventory over complex joins
10. **All operations logged** - check registry_operations_log for audit trail

---

**End of Platform Mapping**
