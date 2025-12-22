# DARX Tools Catalog

**Last Updated:** 2025-12-19
**Purpose:** Complete reference of all tools available to DARX with usage guidance

---

## Tool Categories

1. **Site Management** (6 tools) - Complete site lifecycle management
2. **Client Onboarding** (2 tools) - New client setup
3. **Site Generation & Editing** (2 tools) - Website creation and updates
4. **Platform Operations** (10+ tools) - GitHub, Vercel, Builder.io, GCP
5. **Monitoring & Health** (3 tools) - System health and alerts
6. **Project Management** (2 tools) - Task tracking and collaboration
7. **Self-Management** (5 tools) - DARX's own capabilities

---

## 1. Site Management Tools (NEW - Phase 5)

### list_darx_sites
**When to use:** User asks "what sites do we have", needs site inventory, or wants filtered list
**Returns:** Site list with status, health, GitHub repo, Vercel URL, Builder.io space
**Parameters:**
- `status`: 'active', 'deleted', 'all'
- `health_status`: 'healthy', 'degraded', 'down'
- `limit`: Max results (default 50)

**Example:**
```
User: "Show me all sites"
DARX: Calls list_darx_sites()
```

### get_site_details
**When to use:** Before modifying any site, investigating issues, or user asks about specific site
**Returns:** EVERYTHING - Supabase data, deployments, health history, operations log
**Parameters:**
- `client_slug`: e.g., 'acme-corp'

**Example:**
```
User: "Tell me about acme-corp"
DARX: Calls get_site_details('acme-corp')
```

### delete_site
**When to use:** User explicitly requests site deletion (ALWAYS confirm first!)
**Critical:** This is soft delete with 30-day recovery - NOT permanent
**Returns:** Deleted site ID, recovery deadline, platform results
**Parameters:**
- `client_slug`: Site to delete
- `deleted_by`: Who requested (user email)
- `reason`: REQUIRED for audit
- `confirm`: MUST be true (safety check)

**Example:**
```
User: "Delete acme-corp"
DARX: Asks for confirmation
User: "Yes, delete it"
DARX: Calls delete_site('acme-corp', 'user@email.com', 'Client requested', confirm=True)
```

### recover_deleted_site
**When to use:** User wants to restore a deleted site (within 30 days)
**Returns:** New client ID, platform restoration results
**Parameters:**
- `client_slug`: Site to recover
- `recovered_by`: Who requested recovery

**Example:**
```
User: "Recover acme-corp"
DARX: Calls recover_deleted_site('acme-corp', 'user@email.com')
```

### get_site_health
**When to use:** Quick health status check (cached data)
**Returns:** Latest health check from database
**Parameters:**
- `client_slug`: Site to check

### check_site_health
**When to use:** Want FRESH health data, investigating issues, after deployments
**Returns:** Real-time health across all platforms
**Parameters:**
- `client_slug`: Site to check

---

## 2. Client Onboarding Tools

### start_client_onboarding
**When to use:** User wants to add a new client
**Returns:** Client ID, onboarding form URL
**Parameters:**
- `client_name`: Display name
- `contact_email`: Primary contact
- `website_type`: 'marketing', 'ecommerce', etc.
- `tier`: 'entry', 'standard', 'premium'

### trigger_client_provisioning
**When to use:** After onboarding form submitted, user says "proceed with onboarding"
**Returns:** Provisioning message ID, status
**Parameters:**
- `client_slug`: Client identifier

**Workflow:**
```
1. start_client_onboarding → Creates Supabase record
2. trigger_client_provisioning → Publishes to Pub/Sub
3. darx-provisioner → Provisions all resources
```

---

## 3. Site Generation & Editing

### generate_website
**When to use:** Create initial site from templates
**Parameters:**
- `client_slug`: Client identifier
- `template`: Template to use
- `customizations`: Optional customizations

### edit_darx_site
**When to use:** Update existing site content or structure
**Parameters:**
- `client_slug`: Site to edit
- `operation`: 'update_content', 'add_page', etc.
- `changes`: Description of changes

---

## 4. Platform Operations

### query_supabase
**When to use:** Query database (read-only for non-admins)
**Operations:**
- `select`: Read data
- `insert`: Create records (admin only)
- `update`: Modify records (admin only)
- `delete`: Remove records (admin only)

### manage_builderio
**When to use:** Builder.io CMS operations
**Operations:**
- `get_content`: Retrieve content
- `publish_content`: Publish changes
- `create_space`: Create new space (admin only)

### access_gcp
**When to use:** GCP operations (most require admin)
**Services:**
- `storage`: GCS operations
- `secretmanager`: Manage secrets
- `run`: Cloud Run services
- `pubsub`: Pub/Sub operations

### trigger_cloud_build
**When to use:** Trigger deployments, rebuilds
**Parameters:**
- `service`: Service to deploy
- `branch`: Git branch

---

## 5. Monitoring & Health

### monitor_health
**When to use:** Check system health, service status
**Returns:** Status of all DARX services

### analyze_costs
**When to use:** User asks about costs, budget tracking
**Returns:** Cost breakdown by service

### interact_with_slack
**When to use:** Send messages, update channels, notifications
**Operations:**
- `send_message`: Send to channel/user
- `update_message`: Edit existing message
- `add_reaction`: React to message

---

## 6. Project Management

### manage_projects
**When to use:** Long-running project tracking (admin only)
**Operations:**
- `create_project`: Start new project workspace
- `update_project`: Update status/notes
- `list_projects`: View all projects
- `complete_project`: Mark done

### manage_todos
**When to use:** Multi-step task tracking (automatic for complex tasks)
**Operations:**
- `create`: Create todo list
- `update`: Update status
- `complete`: Mark task done
- `get`: Retrieve current todos

---

## 7. Self-Management Tools

### inspect_self
**When to use:** DARX needs to understand its own code, capabilities
**Operations:**
- `read_file`: Read DARX source code
- `list_files`: List available files
- `search_code`: Search for patterns

### modify_self (via GitHub PR)
**When to use:** DARX needs to update its own code (admin only)
**Process:**
1. Creates GitHub branch
2. Makes code changes
3. Opens pull request
4. Requires human approval

### check_capabilities
**When to use:** Verify tool availability before using
**Returns:** Available tools, permissions

### execute_cli
**When to use:** Execute CLI commands (validated per-service)
**Parameters:**
- `service`: Service to execute on
- `command`: Command to run

### track_operation
**When to use:** Internal checkpoint tracking for complex operations
**Returns:** Operation status, checkpoints

---

## Tool Selection Guide

### "I need to know what sites exist"
→ **list_darx_sites**

### "Tell me about a specific site"
→ **get_site_details**

### "Create a new site"
→ **start_client_onboarding** → **trigger_client_provisioning**

### "Delete a site"
→ **delete_site** (after confirmation)

### "Restore a deleted site"
→ **recover_deleted_site**

### "Is the site healthy?"
→ **get_site_health** (cached) OR **check_site_health** (real-time)

### "Query the database"
→ **query_supabase**

### "Deploy changes"
→ **trigger_cloud_build**

### "What can I do?"
→ **check_capabilities**

### "Track this project"
→ **manage_projects**

---

## Common Tool Combinations

### Complete Site Deletion
```
1. get_site_details(slug) - Understand current state
2. Confirm with user
3. delete_site(slug, user, reason, confirm=true)
4. list_darx_sites(status='deleted') - Verify in deleted list
```

### Site Health Investigation
```
1. check_site_health(slug) - Trigger fresh check
2. get_site_details(slug) - Get full history
3. query_supabase - Check detailed logs if needed
```

### New Client Onboarding
```
1. start_client_onboarding(name, email, type, tier)
2. trigger_client_provisioning(slug)
3. monitor status via query_supabase
4. Verify with get_site_details(slug)
```

---

## Tool Authorization Levels

### Public (Any User)
- list_darx_sites
- get_site_details
- get_site_health
- check_site_health
- query_supabase (read-only)
- start_client_onboarding

### Admin Only
- delete_site
- recover_deleted_site
- query_supabase (write operations)
- manage_builderio (space creation)
- access_gcp (most operations)
- modify_self
- manage_projects

---

**End of Tools Catalog**
