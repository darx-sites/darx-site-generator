"""
Builder.io API client for creating spaces and registering components
"""

import os
import requests
from typing import Dict, List, Any

# Configuration
BUILDER_PUBLIC_KEY = os.getenv('BUILDER_IO_PUBLIC_KEY')
BUILDER_PRIVATE_KEY = os.getenv('BUILDER_IO_PRIVATE_KEY')
BUILDER_API_URL = 'https://builder.io/api/v1'


def create_space(project_name: str, client_name: str = None) -> Dict[str, Any]:
    """
    Create a new Builder.io space for a client.

    Args:
        project_name: Project identifier (e.g., 'acme-corp')
        client_name: Client name

    Returns:
        {
            'success': bool,
            'space_id': str,
            'space_name': str,
            'public_key': str,
            'error': str (if failed)
        }
    """

    if not BUILDER_PRIVATE_KEY:
        return {
            'success': False,
            'error': 'BUILDER_IO_PRIVATE_KEY not configured'
        }

    try:
        # Create space via Builder.io API
        headers = {
            'Authorization': f'Bearer {BUILDER_PRIVATE_KEY}',
            'Content-Type': 'application/json'
        }

        space_name = client_name or project_name.replace('-', ' ').title()

        payload = {
            'name': space_name,
            'id': project_name  # Use project name as space ID
        }

        print(f"   Creating Builder.io space: {space_name}")

        response = requests.post(
            f'{BUILDER_API_URL}/spaces',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 201 or response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'space_id': data.get('id', project_name),
                'space_name': space_name,
                'public_key': data.get('publicKey', BUILDER_PUBLIC_KEY)
            }
        elif response.status_code == 409:
            # Space already exists
            print(f"   ℹ️  Space already exists: {project_name}")
            return {
                'success': True,
                'space_id': project_name,
                'space_name': space_name,
                'public_key': BUILDER_PUBLIC_KEY,
                'note': 'Space already exists'
            }
        else:
            error_msg = f"Builder.io API error: {response.status_code} - {response.text}"
            print(f"   ❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }

    except requests.RequestException as e:
        error_msg = f"Failed to connect to Builder.io API: {str(e)}"
        print(f"   ❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Builder.io space creation error: {str(e)}'
        }


def register_components(
    space_id: str,
    components: List[str],
    staging_url: str
) -> Dict[str, Any]:
    """
    Register custom components with Builder.io space.

    Args:
        space_id: Builder.io space ID
        components: List of component names to register
        staging_url: URL where components are deployed

    Returns:
        {
            'success': bool,
            'registered': int,
            'error': str (if failed)
        }
    """

    if not BUILDER_PRIVATE_KEY:
        return {
            'success': False,
            'error': 'BUILDER_IO_PRIVATE_KEY not configured'
        }

    if not components:
        return {
            'success': True,
            'registered': 0,
            'note': 'No custom components to register'
        }

    try:
        headers = {
            'Authorization': f'Bearer {BUILDER_PRIVATE_KEY}',
            'Content-Type': 'application/json'
        }

        registered_count = 0

        for component_name in components:
            # Register each component
            payload = {
                'name': component_name,
                'type': 'component',
                'component': {
                    'name': component_name,
                    'tag': component_name
                },
                'image': f'{staging_url}/api/builder/component-preview?name={component_name}'
            }

            response = requests.post(
                f'{BUILDER_API_URL}/spaces/{space_id}/components',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                registered_count += 1
            elif response.status_code == 409:
                # Component already registered
                registered_count += 1
            else:
                print(f"   ⚠️  Failed to register {component_name}: {response.status_code}")

        print(f"   ✅ Registered {registered_count}/{len(components)} components")

        return {
            'success': True,
            'registered': registered_count
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Component registration error: {str(e)}'
        }


def create_initial_page(space_id: str, project_name: str) -> Dict[str, Any]:
    """
    Create initial homepage content in Builder.io.

    Args:
        space_id: Builder.io space ID
        project_name: Project name

    Returns:
        {
            'success': bool,
            'page_url': str,
            'error': str (if failed)
        }
    """

    if not BUILDER_PRIVATE_KEY:
        return {
            'success': False,
            'error': 'BUILDER_IO_PRIVATE_KEY not configured'
        }

    try:
        headers = {
            'Authorization': f'Bearer {BUILDER_PRIVATE_KEY}',
            'Content-Type': 'application/json'
        }

        # Create a basic page entry pointing to the Next.js app
        payload = {
            'name': 'Homepage',
            'data': {
                'url': '/',
                'title': project_name.replace('-', ' ').title()
            },
            'published': 'published'
        }

        response = requests.post(
            f'{BUILDER_API_URL}/spaces/{space_id}/content',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code in [200, 201]:
            data = response.json()
            return {
                'success': True,
                'page_url': f'https://builder.io/content/{data.get("id")}'
            }
        else:
            # Non-critical error - the Next.js app will work without this
            print(f"   ℹ️  Could not create initial page in Builder.io: {response.status_code}")
            return {
                'success': True,
                'note': 'Initial page creation skipped'
            }

    except Exception as e:
        # Non-critical - site will still work
        print(f"   ℹ️  Initial page creation skipped: {str(e)}")
        return {
            'success': True,
            'note': 'Initial page creation skipped'
        }
