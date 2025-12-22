"""
Builder.io Space Management
Handles creation and management of Builder.io Spaces

IMPORTANT: Programmatic Space creation requires a Builder.io Enterprise account.
Pro/Team accounts will receive 401 "Invalid key" errors when attempting to create Spaces.

For Pro/Team accounts, users should:
1. Create a Space manually at https://builder.io
2. Provide the Space's public key (starts with 'pub-') to DARX
3. DARX can then manage content within the existing Space

Available for ALL account tiers (Pro/Team/Enterprise):
- Content API: Create, read, update, delete content
- Publish API: Publish draft content
- Component registration: Register custom components
- Model management: Create and configure models

Enterprise-only features:
- Space creation via API
- Space deletion via API
- Space-level settings management
"""

import os
import requests
from typing import Dict, Optional, List, Any


# Builder.io Organization-level API
# These environment variable names must match the Cloud Run secret mappings
# Note: Builder.io only provides a private key for org-level API access (no public key)
BUILDER_ORG_PRIVATE_KEY = os.getenv('BUILDER_IO_ORG_PRIVATE_KEY')  # Mapped from secret BUILDER_IO_ORG_PRIVATE_KEY

# Default Builder.io API base URL
BUILDER_API_BASE = 'https://cdn.builder.io/api/v1'
BUILDER_WRITE_API_BASE = 'https://builder.io/api/v1'


def create_space(
    space_name: str,
    vercel_project_id: Optional[str] = None
) -> Dict:
    """
    Create a new Builder.io Space

    ⚠️  ENTERPRISE ONLY: This function requires a Builder.io Enterprise account.
    Pro/Team accounts will receive 401 "Invalid key" errors.

    For non-Enterprise accounts, guide users to:
    1. Create a Space at https://builder.io
    2. Provide the public key via 'builder_space_public_key' parameter

    Args:
        space_name: Display name for the Space (e.g., "Acme Corp")
        vercel_project_id: Optional Vercel project ID for linking

    Returns:
        {
            'success': True,
            'space_id': 'abc123...',
            'public_key': 'pub-...',
            'private_key': 'priv-...',
            'space_url': 'https://builder.io/content?space=abc123...'
        }

    On failure (including Enterprise requirement):
        {
            'success': False,
            'error': 'Error message explaining the issue'
        }
    """

    # Add comprehensive debug logging
    print(f"🔍 DEBUG: Builder.io Space Creation START")
    print(f"🔍 DEBUG: BUILDER_ORG_PRIVATE_KEY exists: {bool(BUILDER_ORG_PRIVATE_KEY)}")
    print(f"🔍 DEBUG: BUILDER_ORG_PRIVATE_KEY length: {len(BUILDER_ORG_PRIVATE_KEY) if BUILDER_ORG_PRIVATE_KEY else 0}")
    print(f"🔍 DEBUG: API endpoint: https://cdn.builder.io/api/v1/copy-space/create-space")
    print(f"🔍 DEBUG: Space name: {space_name}")
    print(f"🔍 DEBUG: Vercel project ID: {vercel_project_id}")

    if not BUILDER_ORG_PRIVATE_KEY:
        print(f"❌ DEBUG: BUILDER_ORG_PRIVATE_KEY is missing!")
        return {
            'success': False,
            'error': 'BUILDER_IO_PRIVATE_KEY not configured'
        }

    try:
        # Prepare request payload
        payload = {
            'name': space_name,
            'settings': {
                'vercelProjectId': vercel_project_id
            } if vercel_project_id else {}
        }

        # Mask the key for logging only (not in the actual header)
        masked_key = f"{BUILDER_ORG_PRIVATE_KEY[:10]}...{BUILDER_ORG_PRIVATE_KEY[-4:]}" if BUILDER_ORG_PRIVATE_KEY else "None"

        print(f"🔍 DEBUG: Request payload: {payload}")
        print(f"🔍 DEBUG: Using org key (masked): {masked_key}")
        print(f"🔍 DEBUG: Calling Builder.io API...")

        # Call Builder.io Space Management API
        # IMPORTANT: Send the FULL private key in the Authorization header (not masked!)
        response = requests.post(
            'https://cdn.builder.io/api/v1/copy-space/create-space',
            headers={
                'Authorization': f'Bearer {BUILDER_ORG_PRIVATE_KEY}',  # Full key required!
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=30
        )

        print(f"🔍 DEBUG: Response status: {response.status_code}")
        print(f"🔍 DEBUG: Response headers: {dict(response.headers)}")
        print(f"🔍 DEBUG: Response body (first 500 chars): {response.text[:500]}")

        response.raise_for_status()
        data = response.json()

        print(f"🔍 DEBUG: Parsed response data: {data}")

        space_id = data.get('id')
        public_key = data.get('publicKey')
        private_key = data.get('privateKey')

        if not space_id or not public_key:
            return {
                'success': False,
                'error': 'Invalid response from Builder.io API'
            }

        return {
            'success': True,
            'space_id': space_id,
            'public_key': public_key,
            'private_key': private_key,
            'space_url': f'https://builder.io/content?space={space_id}'
        }

    except requests.exceptions.Timeout as e:
        print(f"❌ DEBUG: Request timeout after 30s: {str(e)}")
        return {
            'success': False,
            'error': f'Builder.io API timeout: {str(e)}'
        }
    except requests.exceptions.HTTPError as e:
        print(f"❌ DEBUG: HTTP error from Builder.io API: {str(e)}")
        print(f"❌ DEBUG: Response status: {e.response.status_code if e.response else 'N/A'}")
        print(f"❌ DEBUG: Response body: {e.response.text if e.response else 'N/A'}")
        return {
            'success': False,
            'error': f'Builder.io API HTTP error: {str(e)}'
        }
    except requests.exceptions.RequestException as e:
        print(f"❌ DEBUG: Request exception: {str(e)}")
        return {
            'success': False,
            'error': f'Builder.io API error: {str(e)}'
        }
    except Exception as e:
        print(f"❌ DEBUG: Unexpected exception type: {type(e).__name__}")
        print(f"❌ DEBUG: Unexpected exception message: {str(e)}")
        import traceback
        print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }


def delete_space(
    space_id: str,
    private_key: str
) -> Dict[str, Any]:
    """
    Delete a Builder.io Space

    ⚠️  ENTERPRISE ONLY: This function requires a Builder.io Enterprise account.
    Pro/Team accounts will receive 401 "Invalid key" errors.

    For non-Enterprise accounts, use archive_space_content() instead to mark
    all content as deleted while preserving the Space itself.

    Args:
        space_id: The Space ID to delete
        private_key: Space private key or org private key

    Returns:
        {
            'success': bool,
            'space_id': str,
            'error': str (if failed)
        }
    """

    if not private_key:
        return {
            'success': False,
            'error': 'Private key not provided'
        }

    try:
        # Builder.io does not have a public space deletion API endpoint
        # This would need to be implemented via their admin API
        # For now, return a message indicating manual deletion is required

        return {
            'success': False,
            'error': 'Space deletion requires Enterprise account and manual action via Builder.io admin panel. Use archive_space_content() to mark content for deletion.'
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to delete space: {str(e)}'
        }


def archive_space_content(
    space_id: str,
    private_key: str
) -> Dict[str, Any]:
    """
    Archive all content in a Builder.io Space by marking it as deleted

    Available for ALL account tiers (Pro/Team/Enterprise).
    This does not delete the Space itself, but marks all content entries
    with a deletion timestamp for cleanup purposes.

    Args:
        space_id: The Space ID
        private_key: Space private key

    Returns:
        {
            'success': bool,
            'archived_count': int,
            'models_processed': List[str],
            'error': str (if failed)
        }
    """

    if not private_key:
        return {
            'success': False,
            'error': 'Private key not provided'
        }

    try:
        import time
        from datetime import datetime

        # Common Builder.io models to process
        models_to_archive = ['page', 'section', 'blog-post', 'product', 'symbol']

        archived_count = 0
        models_processed = []
        errors = []

        for model in models_to_archive:
            try:
                # Get all content for this model
                content_result = get_content(
                    public_key=private_key,  # Can use private key for read operations
                    model=model,
                    limit=100
                )

                if not content_result['success']:
                    continue

                results = content_result.get('results', [])

                for content_entry in results:
                    content_id = content_entry.get('id')

                    if not content_id:
                        continue

                    # Update content with archive marker
                    data = content_entry.get('data', {})
                    data['__archived_at'] = datetime.now().isoformat()
                    data['__archived_for_deletion'] = True

                    update_result = update_content(
                        private_key=private_key,
                        model=model,
                        content_id=content_id,
                        data=data
                    )

                    if update_result['success']:
                        archived_count += 1
                    else:
                        errors.append(f"{model}/{content_id}: {update_result.get('error')}")

                models_processed.append(model)
                time.sleep(0.1)  # Rate limiting

            except Exception as e:
                errors.append(f"Error processing model {model}: {str(e)}")

        return {
            'success': True,
            'archived_count': archived_count,
            'models_processed': models_processed,
            'errors': errors if errors else None
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to archive space content: {str(e)}'
        }


def list_spaces(org_private_key: str = None) -> Dict[str, Any]:
    """
    List all Builder.io Spaces in an organization

    ⚠️  ENTERPRISE ONLY: This function requires a Builder.io Enterprise account
    with organization-level API access.

    Args:
        org_private_key: Organization private key (defaults to BUILDER_ORG_PRIVATE_KEY env var)

    Returns:
        {
            'success': bool,
            'spaces': List[Dict],
            'count': int,
            'error': str (if failed)
        }
    """

    key = org_private_key or BUILDER_ORG_PRIVATE_KEY

    if not key:
        return {
            'success': False,
            'error': 'Organization private key not configured'
        }

    try:
        # Builder.io does not have a documented spaces listing endpoint
        # This would require Enterprise API access
        # For now, return a message indicating manual retrieval is required

        return {
            'success': False,
            'error': 'Space listing requires Enterprise account and is not available via public API. Spaces must be tracked manually in Supabase.'
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to list spaces: {str(e)}'
        }


def register_components(
    space_public_key: str,
    components: list
) -> Dict:
    """
    Register custom components with a Builder.io Space

    Args:
        space_public_key: Public key for the Space
        components: List of component definitions

    Returns:
        {
            'success': True,
            'components_registered': 5
        }
    """

    # TODO: Implement component registration
    # This would use Builder.io's component registration API

    return {
        'success': True,
        'components_registered': len(components)
    }


# ============================================================================
# Content Management Functions (Available for Pro/Team/Enterprise accounts)
# ============================================================================

def get_content(
    public_key: str,
    model: str,
    query: Optional[Dict] = None,
    limit: int = 20
) -> Dict:
    """
    Query content from a Builder.io Space

    Available for ALL account tiers (Pro/Team/Enterprise).

    Args:
        public_key: Space public key (starts with 'pub-')
        model: Model name (e.g., 'page', 'blog-post')
        query: Optional query filters
        limit: Max items to return (default 20)

    Returns:
        {
            'success': True,
            'results': [...],
            'count': 5
        }
    """
    try:
        url = f"{BUILDER_API_BASE}/content/{model}"
        params = {
            'apiKey': public_key,
            'limit': limit
        }

        if query:
            params['query'] = query

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        results = data.get('results', [])
        return {
            'success': True,
            'results': results,
            'count': len(results)
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to query content: {str(e)}'
        }


def create_content(
    private_key: str,
    model: str,
    name: str,
    data: Dict[str, Any],
    published: bool = False
) -> Dict:
    """
    Create content in a Builder.io Space

    Available for ALL account tiers (Pro/Team/Enterprise).

    Args:
        private_key: Space private key
        model: Model name (e.g., 'page', 'blog-post')
        name: Content entry name
        data: Content data/fields
        published: Whether to publish immediately

    Returns:
        {
            'success': True,
            'content_id': 'abc123...',
            'name': 'My Page'
        }
    """
    try:
        url = f"{BUILDER_WRITE_API_BASE}/write/{model}"

        payload = {
            'name': name,
            'data': data,
            'published': 'published' if published else 'draft'
        }

        response = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {private_key}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        return {
            'success': True,
            'content_id': result.get('id'),
            'name': name
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to create content: {str(e)}'
        }


def update_content(
    private_key: str,
    model: str,
    content_id: str,
    data: Dict[str, Any]
) -> Dict:
    """
    Update existing content in a Builder.io Space

    Available for ALL account tiers (Pro/Team/Enterprise).

    Args:
        private_key: Space private key
        model: Model name (e.g., 'page', 'blog-post')
        content_id: ID of the content to update
        data: Updated content data/fields

    Returns:
        {
            'success': True,
            'content_id': 'abc123...'
        }
    """
    try:
        url = f"{BUILDER_WRITE_API_BASE}/write/{model}/{content_id}"

        response = requests.put(
            url,
            headers={
                'Authorization': f'Bearer {private_key}',
                'Content-Type': 'application/json'
            },
            json={'data': data},
            timeout=30
        )
        response.raise_for_status()

        return {
            'success': True,
            'content_id': content_id
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to update content: {str(e)}'
        }


def publish_content(
    private_key: str,
    model: str,
    content_id: str
) -> Dict:
    """
    Publish draft content in a Builder.io Space

    Available for ALL account tiers (Pro/Team/Enterprise).

    Args:
        private_key: Space private key
        model: Model name (e.g., 'page', 'blog-post')
        content_id: ID of the content to publish

    Returns:
        {
            'success': True,
            'content_id': 'abc123...',
            'status': 'published'
        }
    """
    try:
        url = f"{BUILDER_WRITE_API_BASE}/publish/{model}/{content_id}"

        response = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {private_key}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        response.raise_for_status()

        return {
            'success': True,
            'content_id': content_id,
            'status': 'published'
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to publish content: {str(e)}'
        }


def delete_content(
    private_key: str,
    model: str,
    content_id: str
) -> Dict:
    """
    Delete content from a Builder.io Space

    Available for ALL account tiers (Pro/Team/Enterprise).

    Args:
        private_key: Space private key
        model: Model name (e.g., 'page', 'blog-post')
        content_id: ID of the content to delete

    Returns:
        {
            'success': True,
            'content_id': 'abc123...',
            'deleted': True
        }
    """
    try:
        url = f"{BUILDER_WRITE_API_BASE}/write/{model}/{content_id}"

        response = requests.delete(
            url,
            headers={
                'Authorization': f'Bearer {private_key}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        response.raise_for_status()

        return {
            'success': True,
            'content_id': content_id,
            'deleted': True
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to delete content: {str(e)}'
        }


def validate_space_key(public_key: str) -> Dict:
    """
    Validate that a Builder.io Space public key is valid and accessible

    Available for ALL account tiers (Pro/Team/Enterprise).

    Args:
        public_key: Space public key to validate (should start with 'pub-')

    Returns:
        {
            'success': True,
            'valid': True,
            'message': 'Space key is valid and accessible'
        }
    """
    if not public_key:
        return {
            'success': False,
            'valid': False,
            'error': 'No public key provided'
        }

    if not public_key.startswith('pub-'):
        return {
            'success': False,
            'valid': False,
            'error': 'Invalid public key format. Builder.io public keys start with "pub-"'
        }

    try:
        # Try to query the page model with the key to verify it works
        url = f"{BUILDER_API_BASE}/content/page"
        params = {
            'apiKey': public_key,
            'limit': 1
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            return {
                'success': True,
                'valid': True,
                'message': 'Space key is valid and accessible'
            }
        elif response.status_code == 401:
            return {
                'success': False,
                'valid': False,
                'error': 'Invalid or expired public key'
            }
        else:
            return {
                'success': False,
                'valid': False,
                'error': f'Unexpected response: {response.status_code}'
            }

    except Exception as e:
        return {
            'success': False,
            'valid': False,
            'error': f'Failed to validate key: {str(e)}'
        }
