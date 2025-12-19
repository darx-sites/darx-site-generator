# Fix test-client-3 Vercel Environment Variables

## Problem
The site https://test-client-3.vercel.app/ is stuck on "Loading..." because the Vercel deployment is missing required environment variables.

## Root Cause
The site-generator was missing `BUILDER_SPACE_MODE` environment variable during deployment, which tells the Next.js site whether to use SHARED or DEDICATED Builder.io space mode.

## Solution Applied

### 1. Fixed site-generator (DONE)
- Added `BUILDER_SPACE_MODE` to env vars passed to Vercel during deployment
- File: `/Users/marvinromero/darx-site-generator/main.py` lines 311-321
- Future deployments will automatically have this env var set

### 2. Manual Fix for test-client-3 (REQUIRED)

Since test-client-3 was deployed before the fix, you need to manually set the environment variables on the Vercel project.

## Manual Steps to Fix test-client-3

### Option A: Via Vercel Dashboard (Easiest)

1. Go to https://vercel.com/
2. Navigate to the `test-client-3` project
3. Go to Settings → Environment Variables
4. Add these variables:

   | Variable Name | Value | Target |
   |---------------|-------|--------|
   | `NEXT_PUBLIC_BUILDER_API_KEY` | `087ba8f548064e72a979ecb3cc500e4c` | Production, Preview, Development |
   | `BUILDER_SPACE_MODE` | `SHARED` | Production, Preview, Development |

5. Go to Deployments tab
6. Find the latest deployment
7. Click "Redeploy"

The site should now work correctly.

### Option B: Via Vercel CLI (If you have it installed)

```bash
cd /path/to/test-client-3
vercel env add NEXT_PUBLIC_BUILDER_API_KEY
# Paste: 087ba8f548064e72a979ecb3cc500e4c
# Select all targets

vercel env add BUILDER_SPACE_MODE
# Paste: SHARED
# Select all targets

vercel --prod
```

### Option C: Via Vercel API (Programmatic)

If you have a valid Vercel token, run this script:

```bash
#!/bin/bash

# Set variables
VERCEL_TOKEN="your_vercel_token_here"
PROJECT_NAME="test-client-3"

# Get project ID
PROJECT_ID=$(curl -s "https://api.vercel.com/v9/projects/${PROJECT_NAME}" \
  -H "Authorization: Bearer ${VERCEL_TOKEN}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "Project ID: $PROJECT_ID"

# Set NEXT_PUBLIC_BUILDER_API_KEY
curl -X POST "https://api.vercel.com/v10/projects/${PROJECT_ID}/env" \
  -H "Authorization: Bearer ${VERCEL_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "NEXT_PUBLIC_BUILDER_API_KEY",
    "value": "087ba8f548064e72a979ecb3cc500e4c",
    "type": "encrypted",
    "target": ["production", "preview", "development"]
  }'

# Set BUILDER_SPACE_MODE
curl -X POST "https://api.vercel.com/v10/projects/${PROJECT_ID}/env" \
  -H "Authorization: Bearer ${VERCEL_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "BUILDER_SPACE_MODE",
    "value": "SHARED",
    "type": "encrypted",
    "target": ["production", "preview", "development"]
  }'

# Trigger redeploy
LATEST_DEPLOYMENT=$(curl -s "https://api.vercel.com/v6/deployments?projectId=${PROJECT_ID}&limit=1" \
  -H "Authorization: Bearer ${VERCEL_TOKEN}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['deployments'][0]['uid'])")

curl -X POST "https://api.vercel.com/v13/deployments/${LATEST_DEPLOYMENT}/redeploy" \
  -H "Authorization: Bearer ${VERCEL_TOKEN}"
```

## Verification

After applying the fix, verify the site works:

1. Visit https://test-client-3.vercel.app/
2. Should display the home page content instead of "Loading..."
3. Visit https://test-client-3.vercel.app/about
4. Should display the about page content

## Expected Behavior

After the fix:
- Home page (`/`) should display: "Welcome to Test Client 3"
- About page (`/about`) should display: "About Test Client 3"

Both pages will have minimal content (just titles and basic text) because these are placeholder pages created by `initialize_builder_content()`. To add rich content, you can:

1. Log into https://builder.io
2. Navigate to the DARX Shared Space (public key: `087ba8f548064e72a979ecb3cc500e4c`)
3. Edit the content for test-client-3 using the visual editor
4. The site will automatically fetch and display the updated content

## Future Deployments

All future deployments via the site-generator will automatically have `BUILDER_SPACE_MODE` set correctly, so this manual fix won't be needed again.
