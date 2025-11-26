# DARX Production Pipeline Roadmap

**Date:** November 25, 2025
**Status:** In Progress - Phase 1 Complete

---

## Recent Accomplishments

### ✅ SMART-STOP Mechanism (Deployed Today)
**Problem Identified:**
- DARX's anti-stop mechanism was preventing legitimate plan presentations
- When DARX presented website generation plans (e.g., "Here's what I'll build... Proceed with this plan?"), the anti-stop logic detected phrases like "let me start" and forced continuation
- Result: DARX would loop endlessly, eventually hitting max reasoning steps without waiting for user approval

**Solution Implemented:**
- Added intelligent detection for "waiting for confirmation" patterns
- Updated `main.py` lines 2810-2843 with SMART-STOP logic
- System now recognizes phrases like:
  - "Proceed with this plan?"
  - "Reply 'yes' to build"
  - "Tell me what to change"
  - "Sound good?"
- When detected, logs: `✅ SMART-STOP: Detected legitimate plan presentation (waiting for user confirmation)`
- Anti-stop and anti-acknowledgment mechanisms now skip forcing continuation when DARX is legitimately waiting

**Files Modified:**
- `/Users/marvinromero/darx-reasoning-function/claude code files/deployment_package/main.py`
  - Lines 2810-2843: Added waiting_for_confirmation detection
  - Lines 2856-2860: Updated ANTI-ACK to respect confirmation waits
  - Lines 2835-2838: Added logging for smart detection

**Deployment:**
- Built: `a4997d61-0d83-48f7-bc0b-d56fe44f7244` (SUCCESS)
- Deployed: `darx-reasoning-00262-shz` (LIVE)
- URL: https://darx-reasoning-474964350921.us-central1.run.app

---

## Full Production Pipeline Architecture

### Overview
The production pipeline connects three systems:
1. **digitalarchitex.com** - Main product site (account management, subscriptions)
2. **HubSpot CRM** - Client relationship management and deal tracking
3. **darx.site** - Generated client websites (the product)

### Phase 1: HubSpot Integration (Next Priority)

#### 1.1 Use Existing HubSpot Setup
- **Secret:** `HUBSPOT_PRIVATE_APP_TOKEN` (already exists in GCP Secret Manager)
- **Available Scopes:**
  - `crm.objects.contacts.read` / `write`
  - `crm.objects.companies.read` / `write`
  - `crm.objects.deals.read` / `write`
  - `crm.objects.owners.read`
  - `crm.lists.write`
  - `crm.schemas.*` (contacts, companies, deals)
  - `forms`, `tickets`, `oauth`

#### 1.2 Create HubSpot Tool for DARX
**File to Create:** `/Users/marvinromero/darx-reasoning-function/claude code files/deployment_package/darx/tools/hubspot_tool.py`

**Tool Definition:**
```python
hubspot_tool = {
    "name": "query_hubspot_client",
    "description": """Query HubSpot CRM for client information to build comprehensive understanding before generating site.

    This tool retrieves:
    - Company profile (name, industry, size, description)
    - Contact details (email, phone, role)
    - Website goals and requirements
    - Past interactions and notes
    - Deal stage and value
    - Custom properties (target audience, brand guidelines, etc.)

    Use this BEFORE presenting a site generation plan to gather client context.""",
    "parameters": {
        "email": {
            "type": "string",
            "description": "Client's email address to lookup contact"
        },
        "company_name": {
            "type": "string",
            "description": "Company name (optional if email provided)"
        }
    }
}

def query_hubspot_client(email: str = None, company_name: str = None) -> Dict[str, Any]:
    """
    Query HubSpot for client information.

    Returns:
        {
            'success': bool,
            'contact': {
                'id': str,
                'email': str,
                'firstname': str,
                'lastname': str,
                'company': str
            },
            'company': {
                'id': str,
                'name': str,
                'industry': str,
                'domain': str,
                'description': str
            },
            'deal': {
                'stage': str,
                'amount': float,
                'close_date': str
            },
            'notes': List[str],  # Recent activity notes
            'custom_properties': {
                'website_goal': str,
                'target_audience': str,
                'brand_colors': str,
                'competitors': List[str]
            },
            'error': str  # if failed
        }
    """
```

#### 1.3 Enhanced DARX Workflow
**Before (Current):**
```
User: "@DARX build a website for Bean There coffee shop"
DARX: [Presents generic plan with assumptions]
User: "yes"
DARX: [Calls generate_website]
```

**After (With HubSpot Integration):**
```
User: "@DARX build a website for marvin@acmecorp.com"
DARX: [Calls query_hubspot_client(email="marvin@acmecorp.com")]
DARX: [Receives: Acme Corp, SaaS industry, B2B target, pricing page priority]
DARX: "I'll build a website for Acme Corp! Based on your HubSpot profile:

**Client Research:**
- Company: Acme Corp (SaaS, B2B, 20-50 employees)
- Industry: Software / Enterprise Solutions
- Target Audience: CTOs and IT Directors at mid-market companies
- Primary Goal: Lead generation via demo requests
- Current Stage: Deal in "Proposal" stage ($5,000 value)
- Past Notes: Requested emphasis on security and compliance features

**Proposed Site Plan:**
- Project: acme-corp.darx.site
- Industry: SaaS
- Design: Professional, trust-building aesthetic
- Sections:
  ✓ Hero: Value proposition for CTOs
  ✓ Security: SOC 2, GDPR compliance badges
  ✓ Features: Enterprise feature highlights
  ✓ Pricing: Tiered pricing with ROI calculator
  ✓ Demo Form: Integrated with HubSpot for lead capture
  ✓ Case Studies: 2-3 success stories
  ✓ Contact: Multiple CTAs for demo requests

**Custom Features:**
- Spline 3D product demo
- HubSpot form integration (auto-creates deals)
- Calendly integration for demo booking
- Trust badges and certifications section

Estimated Time: 2-3 minutes
Result: acme-corp.darx.site

Proceed with this plan? Reply 'yes' to build, or tell me what to adjust."

User: "yes"
DARX: [Calls generate_website with enriched client_info]
```

#### 1.4 Implementation Tasks
1. Create `darx/tools/hubspot_tool.py`
2. Implement `query_hubspot_client()` function
3. Add HubSpot API client wrapper
4. Register tool in `darx/tools/__init__.py`
5. Update `main.py` to load HUBSPOT_PRIVATE_APP_TOKEN secret
6. Test with real HubSpot data
7. Update site_generation_tool instructions to encourage HubSpot lookup first

---

### Phase 2: Memberstack Integration (After HubSpot)

#### 2.1 Memberstack Setup on digitalarchitex.com
**Product Site:** digitalarchitex.com (where clients manage accounts)

**Signup Form Fields:**
- Name (required)
- Email (required)
- Company Name (required)
- Industry (dropdown: SaaS, E-commerce, Healthcare, Real Estate, Restaurant, General)
- Website Goal (textarea: "Describe what you want your website to achieve")
- Phone (optional)
- How did you hear about us? (optional)

**Memberstack Configuration:**
- Webhook URL: `https://darx-reasoning-474964350921.us-central1.run.app/webhook/member-signup`
- Webhook Events: `member.created`, `member.updated`
- Auth Method: Magic link + Password
- Plans: Free Trial (7 days), Pro ($49/mo), Business ($149/mo)

#### 2.2 Webhook Handler Implementation
**File to Create:** `/Users/marvinromero/darx-reasoning-function/claude code files/deployment_package/webhook_handlers.py`

```python
from fastapi import Request, HTTPException
from typing import Dict, Any
import requests

@app.post("/webhook/member-signup")
async def handle_member_signup(request: Request):
    """
    Handle new member signup from Memberstack.

    Flow:
    1. Validate Memberstack webhook signature
    2. Extract member data
    3. Create/update HubSpot contact + company
    4. Trigger site generation (or queue for approval)
    5. Update HubSpot deal with generated site URL
    6. Send welcome email to member
    """

    # 1. Validate webhook
    signature = request.headers.get('memberstack-signature')
    payload = await request.json()

    if not verify_memberstack_signature(signature, payload):
        raise HTTPException(status_code=401, detail="Invalid signature")

    member_data = payload.get('data', {})

    # 2. Extract member info
    member_info = {
        'email': member_data.get('email'),
        'name': member_data.get('name'),
        'company_name': member_data.get('customFields', {}).get('company_name'),
        'industry': member_data.get('customFields', {}).get('industry'),
        'website_goal': member_data.get('customFields', {}).get('website_goal'),
        'phone': member_data.get('customFields', {}).get('phone'),
        'plan': member_data.get('planId')  # Free, Pro, Business
    }

    # 3. Create HubSpot contact + company
    from darx.tools.hubspot_tool import create_hubspot_contact
    hubspot_result = create_hubspot_contact(member_info)
    contact_id = hubspot_result['contact_id']
    company_id = hubspot_result['company_id']

    # 4. Decide: Auto-generate or Manual approval?
    if member_info['plan'] in ['pro', 'business']:
        # Paid plans: Auto-generate site immediately
        site_result = await trigger_auto_generation(member_info)

        # 5. Update HubSpot deal
        from darx.tools.hubspot_tool import update_hubspot_deal
        update_hubspot_deal(
            contact_id=contact_id,
            deal_data={
                'dealstage': 'site_generated',
                'site_url': site_result['custom_url'],
                'github_repo': site_result['github_repo']
            }
        )

        # 6. Send welcome email with site URL
        send_welcome_email(
            email=member_info['email'],
            name=member_info['name'],
            site_url=site_result['custom_url'],
            plan=member_info['plan']
        )

    else:
        # Free trial: Queue for manual approval
        queue_for_manual_approval(member_info, contact_id)

        # Send "under review" email
        send_review_email(member_info['email'], member_info['name'])

    return {
        'success': True,
        'contact_id': contact_id,
        'company_id': company_id
    }


async def trigger_auto_generation(member_info: Dict) -> Dict:
    """
    Trigger automatic site generation for new member.
    Uses darx-site-generator service directly.
    """

    from darx.clients.site_generator import generate_site

    project_name = member_info['company_name'].lower().replace(' ', '-')

    result = generate_site(
        project_name=project_name,
        requirements=member_info['website_goal'],
        industry=member_info['industry'],
        client_info={
            'company_name': member_info['company_name'],
            'contact_email': member_info['email'],
            'industry': member_info['industry'],
            'website_goal': member_info['website_goal']
        },
        features=[]  # Default features based on plan
    )

    return result


def send_welcome_email(email: str, name: str, site_url: str, plan: str):
    """Send welcome email with site URL."""

    # Use SendGrid, Mailgun, or your email service
    # Template: Welcome to DARX! Your site is ready.

    email_html = f"""
    <h1>Welcome to DARX, {name}! 🎉</h1>

    <p>Your personalized website is ready!</p>

    <p><strong>Your Site:</strong> <a href="{site_url}">{site_url}</a></p>

    <h2>What's Next?</h2>
    <ul>
        <li>Visit your site and see your content live</li>
        <li>Edit visually in Builder.io (no code required)</li>
        <li>Connect your custom domain</li>
        <li>Manage your subscription at digitalarchitex.com/dashboard</li>
    </ul>

    <p>Your Plan: {plan.title()}</p>

    <p>Need help? Reply to this email or visit our support page.</p>

    <p>Thanks,<br>The DARX Team</p>
    """

    # Send via your email provider
```

#### 2.3 HubSpot Helper Functions
**Add to:** `darx/tools/hubspot_tool.py`

```python
def create_hubspot_contact(member_info: Dict) -> Dict:
    """
    Create or update HubSpot contact and company.

    Returns:
        {
            'contact_id': str,
            'company_id': str,
            'deal_id': str
        }
    """
    import requests
    import os

    token = os.getenv('HUBSPOT_PRIVATE_APP_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # 1. Create/update contact
    contact_data = {
        'properties': {
            'email': member_info['email'],
            'firstname': member_info['name'].split()[0],
            'lastname': ' '.join(member_info['name'].split()[1:]) if len(member_info['name'].split()) > 1 else '',
            'company': member_info['company_name'],
            'phone': member_info.get('phone', ''),
            'industry': member_info['industry'],
            'website_goal': member_info['website_goal'],
            'lifecyclestage': 'customer',
            'hs_lead_status': 'NEW'
        }
    }

    # Search for existing contact
    search_response = requests.post(
        'https://api.hubapi.com/crm/v3/objects/contacts/search',
        headers=headers,
        json={'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': member_info['email']}]}]}
    )

    if search_response.json().get('total', 0) > 0:
        # Update existing
        contact_id = search_response.json()['results'][0]['id']
        requests.patch(
            f'https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}',
            headers=headers,
            json=contact_data
        )
    else:
        # Create new
        response = requests.post(
            'https://api.hubapi.com/crm/v3/objects/contacts',
            headers=headers,
            json=contact_data
        )
        contact_id = response.json()['id']

    # 2. Create company
    company_data = {
        'properties': {
            'name': member_info['company_name'],
            'industry': member_info['industry'],
            'domain': f"{member_info['company_name'].lower().replace(' ', '-')}.darx.site"
        }
    }

    company_response = requests.post(
        'https://api.hubapi.com/crm/v3/objects/companies',
        headers=headers,
        json=company_data
    )
    company_id = company_response.json()['id']

    # 3. Associate contact with company
    requests.put(
        f'https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/company/{company_id}/contact_to_company'
    )

    # 4. Create deal
    deal_data = {
        'properties': {
            'dealname': f"Website for {member_info['company_name']}",
            'dealstage': 'site_pending',
            'amount': 49 if member_info.get('plan') == 'pro' else 149,
            'pipeline': 'default'
        }
    }

    deal_response = requests.post(
        'https://api.hubapi.com/crm/v3/objects/deals',
        headers=headers,
        json=deal_data
    )
    deal_id = deal_response.json()['id']

    # Associate deal with contact and company
    requests.put(
        f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}/associations/contact/{contact_id}/deal_to_contact'
    )
    requests.put(
        f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}/associations/company/{company_id}/deal_to_company'
    )

    return {
        'contact_id': contact_id,
        'company_id': company_id,
        'deal_id': deal_id
    }


def update_hubspot_deal(contact_id: str, deal_data: Dict):
    """Update HubSpot deal with site generation results."""

    # Implementation to update deal properties
    # Including: site_url, github_repo, generation_date, dealstage
```

#### 2.4 Full Production Flow
**End-to-End User Journey:**

1. **User visits digitalarchitex.com** → Lands on homepage
2. **Signs up with Memberstack** → Enters: name, email, company, industry, website goal
3. **Memberstack webhook fires** → `POST /webhook/member-signup`
4. **Webhook handler executes:**
   - Validates signature
   - Creates HubSpot contact
   - Creates HubSpot company
   - Associates contact → company
   - Creates deal: "Website for [Company]"
5. **Site generation:**
   - **If paid plan (Pro/Business):** Auto-generate immediately
   - **If free trial:** Queue for manual approval
6. **Site generated:**
   - Creates Next.js site via darx-site-generator
   - Pushes to GitHub: `darx-sites/[company-slug]`
   - Deploys to Vercel
   - Creates CNAME: `[company-slug].darx.site`
7. **HubSpot updated:**
   - Deal stage: "site_generated"
   - Custom properties: site_url, github_repo
8. **User receives email:**
   - Subject: "Your DARX site is ready! 🎉"
   - Body: Site URL, Builder.io edit link, next steps
9. **User can:**
   - Visit their live site
   - Edit in Builder.io
   - Connect custom domain
   - Manage subscription at digitalarchitex.com/dashboard

---

## Implementation Roadmap

### ✅ Completed
- [x] Fixed anti-stop mechanism with SMART-STOP detection
- [x] Deployed darx-reasoning with SMART-STOP (revision 00262-shz)
- [x] Verified darx-site-generator working (coffee-test-v3 successful)
- [x] Confirmed HubSpot secret exists in GCP Secret Manager

### 🔄 Next Steps (Tomorrow - Priority Order)

#### Step 1: Test DARX with SMART-STOP Fix
**Goal:** Verify DARX can present plans and wait for approval

**Test Case:**
- Send in Slack: "@DARX build a test website for Bean There coffee shop"
- Expected: DARX presents detailed plan with "Proceed with this plan?"
- Expected Log: `✅ SMART-STOP: Detected legitimate plan presentation`
- Reply: "yes"
- Expected: DARX calls generate_website tool and returns site URL

**Success Criteria:**
- DARX presents plan without looping
- DARX waits for approval
- After approval, generates site successfully

---

#### Step 2: Implement HubSpot Integration
**Files to Create:**
1. `darx/tools/hubspot_tool.py` - HubSpot API wrapper
2. Update `darx/tools/__init__.py` - Register new tool

**Tasks:**
1. Create `query_hubspot_client()` function
2. Create `create_hubspot_contact()` function
3. Create `update_hubspot_deal()` function
4. Add HUBSPOT_PRIVATE_APP_TOKEN to darx-reasoning environment
5. Test with real HubSpot data (use your Acme Corp contact)
6. Update site_generation_tool description to encourage HubSpot lookup

**Testing:**
- Create test contact in HubSpot
- Test: "@DARX build a site for test@example.com"
- Verify: DARX queries HubSpot and presents enriched plan

**Success Criteria:**
- DARX can query HubSpot by email
- Returns contact + company + deal info
- Plan includes client research section
- Generated sites include HubSpot context

---

#### Step 3: Implement Memberstack Integration
**Files to Create:**
1. `webhook_handlers.py` - Memberstack webhook endpoint
2. Update `main.py` - Register webhook routes

**Tasks:**
1. Set up Memberstack on digitalarchitex.com
2. Configure Memberstack webhook → darx-reasoning
3. Implement `/webhook/member-signup` endpoint
4. Implement auto-generation flow (paid plans)
5. Implement manual approval queue (free trial)
6. Set up email service (SendGrid/Mailgun)
7. Create email templates (welcome, review, site ready)

**Testing:**
- Sign up on digitalarchitex.com with test account
- Verify webhook received
- Verify HubSpot contact created
- Verify site auto-generated
- Verify welcome email sent

**Success Criteria:**
- Webhook handler processes signups
- Creates HubSpot contacts/companies/deals
- Auto-generates sites for paid plans
- Sends welcome emails with site URLs

---

#### Step 4: Test Full Production Pipeline
**End-to-End Test:**
1. Sign up on digitalarchitex.com as test user
2. Enter company: "Test Bakery", industry: "Restaurant"
3. Website goal: "Showcase menu and take online orders"
4. Verify webhook creates HubSpot records
5. Verify site generates: test-bakery.darx.site
6. Verify welcome email arrives
7. Visit site and confirm it's live
8. Edit in Builder.io

**Success Criteria:**
- Complete flow works end-to-end
- No manual intervention required
- User receives site URL within 3 minutes
- Site is editable in Builder.io

---

### 🚀 Future Enhancements (After Pipeline Works)

#### Phase 3: DARX Self-Sufficiency
- Automatic error recovery
- Log analysis and self-debugging
- Self-healing deployments
- Performance monitoring

#### Phase 4: Improve Generated Sites
- Unsplash API for real images
- Better Builder.io component library
- SEO optimization (meta tags, sitemaps)
- Analytics integration (GA4, Plausible)
- Custom domain setup automation

#### Phase 5: Advanced Features
- Client persona building (research competitors, industry trends)
- A/B testing different design approaches
- Automatic content generation (copy, images, videos)
- Multi-page site support
- E-commerce integration (Shopify, Stripe)

---

## Key Files Reference

### Current State
- `darx-reasoning` service: **00262-shz** (LIVE with SMART-STOP)
- `darx-site-generator` service: **00009-8pv** (LIVE, working)
- HubSpot secret: `HUBSPOT_PRIVATE_APP_TOKEN` (exists in Secret Manager)

### Files Modified Today
- `/Users/marvinromero/darx-reasoning-function/claude code files/deployment_package/main.py`
  - Lines 2810-2843: SMART-STOP detection logic

### Files to Create Tomorrow
- `/Users/marvinromero/darx-reasoning-function/claude code files/deployment_package/darx/tools/hubspot_tool.py`
- `/Users/marvinromero/darx-reasoning-function/claude code files/deployment_package/webhook_handlers.py`

---

## Technical Notes

### SMART-STOP Implementation Details
**Pattern Matching:**
The system detects when DARX is legitimately waiting for confirmation by looking for these phrases:
- "proceed with this plan?"
- "reply 'yes' to"
- "tell me what to change"
- "sound good?"
- "approve this?"

**Logic:**
```python
is_waiting_for_confirmation = any(
    indicator in response_lower
    for indicator in waiting_for_confirmation_indicators
)

if looks_premature and not is_waiting_for_confirmation:
    # Force continuation
else:
    # Allow DARX to stop and wait for user
```

### HubSpot API Endpoints
- Search contacts: `POST /crm/v3/objects/contacts/search`
- Get contact: `GET /crm/v3/objects/contacts/{contactId}`
- Create contact: `POST /crm/v3/objects/contacts`
- Update contact: `PATCH /crm/v3/objects/contacts/{contactId}`
- Create company: `POST /crm/v3/objects/companies`
- Create deal: `POST /crm/v3/objects/deals`
- Associations: `PUT /crm/v3/objects/{objectType}/{objectId}/associations/{toObjectType}/{toObjectId}/{associationTypeId}`

### Memberstack Webhook Payload
```json
{
  "type": "member.created",
  "data": {
    "id": "mem_123",
    "email": "user@example.com",
    "name": "John Doe",
    "planId": "pro",
    "customFields": {
      "company_name": "Acme Corp",
      "industry": "saas",
      "website_goal": "Lead generation",
      "phone": "+1234567890"
    },
    "createdAt": "2025-11-25T07:00:00Z"
  }
}
```

---

## Success Metrics

### Short-term (This Week)
- [ ] DARX presents plans and waits for approval (no looping)
- [ ] HubSpot integration returns client data
- [ ] Memberstack webhook creates sites automatically
- [ ] Full pipeline works end-to-end with test user

### Medium-term (Next 2 Weeks)
- [ ] First 10 real clients onboarded via digitalarchitex.com
- [ ] 95%+ success rate for auto-generation
- [ ] Average generation time under 3 minutes
- [ ] Zero manual intervention required

### Long-term (Next Month)
- [ ] 100+ clients with active darx.sites
- [ ] Self-sufficiency features deployed (error recovery)
- [ ] Advanced features (Unsplash, better Builder.io, SEO)
- [ ] Plan iteration (client can request changes)

---

**Document Version:** 1.0
**Last Updated:** November 25, 2025
**Next Review:** Tomorrow (after Step 1 testing)
