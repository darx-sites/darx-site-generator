# DARX System Architecture

**Last Updated:** 2025-12-19
**Purpose:** High-level overview of DARX services, their responsibilities, and how they interact

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         SLACK (User Interface)                   │
│                  Users interact with DARX via Slack              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                   darx-reasoning (Cloud Run)                     │
│  DARX Brain - Anthropic Claude with Function Calling            │
│  - Understands natural language requests                        │
│  - Calls tools to perform actions                               │
│  - 40+ tools for site management, deployment, monitoring        │
│  URL: https://darx-reasoning-slgtfcnoxq-uc.a.run.app           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ↓                      ↓                      ↓
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│darx-provision│    │darx-site-generator│   │  darx-registry   │
│  (Pub/Sub)   │    │   (Cloud Run)     │   │   (Cloud Run)    │
│              │    │                   │   │                   │
│Onboards new  │    │Site generation &  │   │Multiplatform     │
│clients via   │    │management API     │   │orchestration     │
│Pub/Sub topic │    │                   │   │                   │
│              │    │Endpoints:         │   │Services:         │
│Triggered by  │    │/generate          │   │delete_site()     │
│DARX tool     │    │/sites             │   │recover_site()    │
│              │    │/sites/{slug}      │   │health_check()    │
│              │    │/health            │   │inventory_sync()  │
└──────────────┘    └──────────────────┘   └──────────────────┘
        │                    │                      │
        └────────────────────┼──────────────────────┘
                             ↓
        ┌────────────────────────────────────────┐
        │         Platform Integrations          │
        │  GitHub | Vercel | Builder.io | GCS   │
        │  Supabase | Secret Manager | Pub/Sub  │
        └────────────────────────────────────────┘
```

---

## Service Responsibilities

### 1. darx-reasoning (DARX Brain)

**Type:** Cloud Run Service
**Language:** Python (Flask)
**AI Model:** Anthropic Claude Sonnet 4.5
**URL:** https://darx-reasoning-slgtfcnoxq-uc.a.run.app

**Purpose:** DARX's intelligence layer - understands natural language and executes function calls

**Responsibilities:**
- ✅ Process Slack messages from users
- ✅ Understand intent using Claude's reasoning
- ✅ Execute function calls (40+ tools available)
- ✅ Return formatted responses to Slack
- ✅ Maintain conversation context
- ✅ Handle multi-step operations

**Key Tools Provided:**
- Site management (list, details, delete, recover, health)
- Client onboarding
- Site generation
- Builder.io CMS operations
- GitHub operations
- Vercel deployments
- GCP operations
- Supabase queries
- Project management
- Self-modification

**Dependencies:**
- Anthropic API (Claude)
- Slack API
- darx-site-generator API
- darx-registry API
- Supabase
- Secret Manager

---

### 2. darx-provisioner (Onboarding Service)

**Type:** Cloud Run Service (Pub/Sub triggered)
**Language:** Python
**Trigger:** Pub/Sub topic `darx-client-onboarding`

**Purpose:** Automated client onboarding workflow

**Responsibilities:**
- ✅ Generate Next.js site code from templates
- ✅ Create GitHub repository in darx-sites org
- ✅ Create Vercel project with auto-deploy
- ✅ Create/configure Builder.io space
- ✅ Store credentials in Secret Manager
- ✅ Create initial GCS backup
- ✅ Update Supabase with provisioning status

**Workflow:**
1. Receive Pub/Sub message with client data
2. Generate Next.js code using templates
3. Create GitHub repo (`darx-sites/{client-slug}`)
4. Push generated code to GitHub
5. Create Vercel project (auto-links to GitHub)
6. Create Builder.io space (shared or dedicated based on tier)
7. Store Builder.io credentials in Secret Manager
8. Upload code backup to GCS
9. Update Supabase `clients` table: status = 'active'
10. Notify Slack of completion

**Dependencies:**
- GitHub API (PyGithub)
- Vercel API
- Builder.io API
- GCP Secret Manager
- GCS
- Supabase
- Slack API

---

### 3. darx-site-generator (Site Management API)

**Type:** Cloud Run Service
**Language:** Python (Flask)
**URL:** https://darx-site-generator-slgtfcnoxq-uc.a.run.app

**Purpose:** Central API for site operations and management

**Responsibilities:**
- ✅ Generate new sites from templates
- ✅ List all sites with filters
- ✅ Get comprehensive site details
- ✅ Soft delete sites (proxies to darx-registry)
- ✅ Recover deleted sites (proxies to darx-registry)
- ✅ Health checks (proxies to darx-registry)
- ✅ Site editing operations

**API Endpoints:**

```
POST   /generate                    - Generate new site
GET    /sites                       - List all sites
GET    /sites/{slug}                - Get site details
DELETE /sites/{slug}                - Soft delete site
POST   /sites/{slug}/recover        - Recover deleted site
GET    /sites/{slug}/health         - Get cached health status
POST   /sites/{slug}/health/check   - Trigger health check
```

**Dependencies:**
- darx-registry API (for management operations)
- Supabase
- GitHub API
- Builder.io API
- GCS

---

### 4. darx-registry (Multiplatform Orchestrator)

**Type:** Cloud Run Service
**Language:** Python (Flask)
**URL:** https://darx-registry-slgtfcnoxq-uc.a.run.app

**Purpose:** Centralized orchestration for multiplatform operations

**Responsibilities:**
- ✅ Soft delete with 30-day recovery window
- ✅ Site recovery (restore all platforms)
- ✅ Health monitoring across all platforms
- ✅ Inventory synchronization
- ✅ Audit logging for all operations

**Core Services:**

**MultiplatformOrchestrator** - Main orchestration class
```python
delete_site(client_slug, deleted_by, reason)
- Creates snapshot in deleted_sites table
- Archives GitHub repo (rename with ARCHIVED- prefix)
- Pauses Vercel deployments
- Archives Builder.io content
- Tags GCS backups for retention
- Sets 30-day recovery deadline
- Logs all operations

recover_site(deleted_site_id, recovered_by)
- Verifies recovery window not expired
- Restores GitHub repo
- Re-enables Vercel deployments
- Restores Builder.io content
- Creates new client record
- Marks deleted_sites.recovered = true

health_check(client_slug)
- Checks GitHub repo accessibility
- Checks Vercel deployment status
- Checks Builder.io space
- Checks GCS backups
- Checks staging URL
- Stores results in site_health_checks table
- Updates clients.health_status

inventory_sync()
- Queries all platforms for resources
- Updates platform_inventory table
- Detects orphaned resources
- Detects drift
- Updates last_verified_at timestamps
```

**API Endpoints:**

```
GET    /api/v1/sites                     - List sites
GET    /api/v1/sites/{slug}              - Get site details
DELETE /api/v1/sites/{slug}              - Soft delete
POST   /api/v1/sites/{slug}/recover      - Recover site
GET    /api/v1/sites/{slug}/health       - Get health
POST   /api/v1/sites/{slug}/health/check - Trigger check
GET    /api/v1/platforms/inventory       - Full inventory
GET    /api/v1/platforms/orphaned        - Orphaned resources
```

**Dependencies:**
- Supabase
- GitHub API
- Vercel API
- Builder.io API
- GCS

---

## Data Flow Examples

### Site Creation

```
User: "Create a site for Acme Corp"
  ↓
darx-reasoning:
  1. Calls start_client_onboarding tool
  2. Creates record in Supabase clients table
  3. Calls trigger_client_provisioning tool
  4. Publishes to Pub/Sub topic
  ↓
darx-provisioner (triggered by Pub/Sub):
  1. Generates Next.js code
  2. Creates GitHub repo
  3. Creates Vercel project
  4. Creates Builder.io space
  5. Stores credentials in Secret Manager
  6. Creates GCS backup
  7. Updates Supabase: status = 'active'
  8. Notifies Slack
```

### Site Deletion (Soft Delete)

```
User: "Delete acme-corp"
  ↓
darx-reasoning:
  1. Confirms with user
  2. Calls delete_site tool
  ↓
darx-site-generator:
  DELETE /sites/acme-corp
  ↓
darx-registry:
  1. Creates snapshot in deleted_sites
  2. Archives GitHub repo
  3. Marks Vercel for deletion
  4. Archives Builder.io content
  5. Tags GCS backups
  6. Updates Supabase: status = 'deleted'
  7. Sets recovery_deadline = now() + 30 days
  ↓
darx-reasoning:
  Returns success message to user
```

### Health Check

```
User: "Check health of acme-corp"
  ↓
darx-reasoning:
  Calls check_site_health tool
  ↓
darx-site-generator:
  POST /sites/acme-corp/health/check
  ↓
darx-registry:
  1. Checks GitHub repo
  2. Checks Vercel deployment
  3. Checks Builder.io space
  4. Checks GCS backups
  5. Checks staging URL
  6. Stores in site_health_checks table
  7. Updates clients.health_status
  8. Returns aggregated status
  ↓
darx-reasoning:
  Returns health report to user
```

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **AI/ML** | Anthropic Claude Sonnet 4.5 |
| **Backend** | Python 3.11, Flask 3.0 |
| **Database** | Supabase (PostgreSQL) |
| **Hosting** | Google Cloud Run (all services) |
| **Storage** | Google Cloud Storage |
| **Secrets** | GCP Secret Manager |
| **Messaging** | GCP Pub/Sub |
| **Version Control** | GitHub |
| **Deployments** | Vercel |
| **CMS** | Builder.io |
| **Communication** | Slack API |
| **CI/CD** | Cloud Build |

---

## Security Architecture

### Authentication & Authorization

**Service-to-Service:**
- Cloud Run services use Google Cloud identity tokens
- Services authenticate via `Authorization: Bearer {token}` headers

**User Authentication:**
- Slack OAuth for user identity
- Admin users configured via environment variable
- Admin-only operations enforced in darx-reasoning

**Secrets Management:**
- All credentials stored in Secret Manager
- Never in code or Supabase
- IAM-based access control
- Automatic encryption

### Data Security

**At Rest:**
- Supabase: Encrypted PostgreSQL database
- GCS: Server-side encryption
- Secret Manager: Encrypted secrets

**In Transit:**
- All services use HTTPS/TLS
- Cloud Run enforces HTTPS
- Vercel provides automatic SSL

### Access Control

**Admin-Only Operations:**
- Site deletion (soft delete)
- Permanent deletion after 30 days
- Supabase write operations
- GCP infrastructure changes
- Builder.io space creation

**Public Operations:**
- Site listing (read-only)
- Health checks (read-only)
- Site generation (with approval)

---

## Monitoring & Observability

### Logging

**Cloud Logging:**
- All Cloud Run services send logs to Cloud Logging
- Structured JSON logging
- Searchable by service, severity, timestamp

**Supabase:**
- registry_operations_log table for audit trail
- Every operation logged with:
  - Who initiated
  - What operation
  - Platform results
  - Success/failure counts
  - Timestamps

### Health Monitoring

**Automated:**
- Health checks stored in site_health_checks table
- Can be scheduled (future: Cloud Scheduler)
- Tracks historical health trends

**Manual:**
- DARX can trigger health checks via check_site_health tool
- Users can request health status anytime

### Alerting (Future)

**Planned:**
- Slack alerts for degraded sites
- Email notifications for deleted sites approaching 30-day deadline
- Cost alerts for budget overruns

---

## Scalability Considerations

### Current Architecture

**Serverless:** All services on Cloud Run
- Auto-scales to zero when idle
- Scales up based on demand
- Pay per request

**Database:** Supabase (managed PostgreSQL)
- Connection pooling
- Read replicas available (if needed)
- Scales with plan tier

**Storage:** GCS
- Unlimited scalability
- 11 nines durability
- Global CDN

### Bottlenecks (Future)

**Potential Issues:**
- Anthropic API rate limits (currently generous)
- Supabase connection limits (configurable)
- GitHub API rate limits (5000 requests/hour)
- Builder.io API rate limits (tier-dependent)

**Mitigation:**
- Caching for frequently accessed data
- Rate limit handling with exponential backoff
- Connection pooling for Supabase
- Batching operations where possible

---

## Deployment Architecture

### CI/CD Pipeline

**Cloud Build:**
```
Code pushed to GitHub
  ↓
GitHub webhook triggers Cloud Build
  ↓
Cloud Build:
  1. Builds Docker image
  2. Runs tests (if configured)
  3. Pushes to Container Registry
  4. Deploys to Cloud Run
  5. Updates service with new revision
```

**Build Triggers:**
- darx-reasoning: Pushes to main branch
- darx-site-generator: Pushes to main branch
- darx-registry: Pushes to main branch

### Environments

**Production:**
- All services deployed to Cloud Run
- Project: sylvan-journey-474401-f9
- Region: us-central1

**No Staging Environment Currently:**
- All deployments go to production
- Future: Add staging environment for testing

---

## Cost Structure

| Service | Cost Model | Estimated Monthly |
|---------|------------|-------------------|
| **Cloud Run** | Per request + compute time | $10-50 (low traffic) |
| **Anthropic API** | Per token (input/output) | $50-200 (varies by usage) |
| **Supabase** | Tiered (Free → Pro → Enterprise) | $0-25 (Free tier currently) |
| **GCS** | Storage + operations | $5-20 |
| **Secret Manager** | Per secret version | <$5 |
| **Vercel** | Per deployment (Hobby free) | $0 (Hobby tier) |
| **Builder.io** | Per space | Varies by client tier |
| **GitHub** | Free (public repos) | $0 |
| **Pub/Sub** | Per message | <$5 |
| **Cloud Build** | Build minutes | $0 (free tier 120 mins/day) |

**Total Estimated:** $65-300/month (scales with usage)

---

## Future Enhancements

### Phase 7: Health Monitoring Automation
- Scheduled health checks (Cloud Scheduler)
- Slack alerts for degraded sites
- Monitoring dashboard

### Phase 8: Soft Delete Automation
- Scheduled permanent deletion after 30 days
- Email warnings at 7-day, 1-day before deadline
- Admin confirmation for permanent delete

### Advanced Features
- Rollback deployments to previous versions
- A/B testing infrastructure
- Analytics integration
- Custom domain support
- Multi-region deployments

---

**End of Architecture Overview**
