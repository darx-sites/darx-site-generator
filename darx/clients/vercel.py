"""
Vercel deployment integration
"""

import os
import requests
from typing import Dict, Any

VERCEL_TOKEN = os.getenv('VERCEL_TOKEN')
VERCEL_TEAM_ID = os.getenv('VERCEL_TEAM_ID')


def deploy_to_vercel(
    project_name: str,
    github_repo: str,
    env_vars: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Deploy project to Vercel.

    Args:
        project_name: Vercel project name (e.g., 'acme-corp')
        github_repo: GitHub repo in format 'org/repo' (e.g., 'darx-sites/acme-corp')
        env_vars: Environment variables for the project

    Returns:
        {
            'success': bool,
            'staging_url': str,
            'production_url': str,
            'error': str (if failed)
        }
    """

    if not VERCEL_TOKEN:
        return {
            'success': False,
            'error': 'VERCEL_TOKEN not configured'
        }

    env_vars = env_vars or {}

    try:
        headers = {
            'Authorization': f'Bearer {VERCEL_TOKEN}',
            'Content-Type': 'application/json'
        }

        # Step 1: Check if project exists
        project = _get_or_create_project(project_name, github_repo, headers)
        if not project:
            raise Exception("Failed to create or get Vercel project")

        project_id = project['id']

        # Step 2: Set environment variables
        if env_vars:
            _set_env_vars(project_id, env_vars, headers)

        # Step 3: Trigger deployment
        # Extract repoId from project link
        repo_id = project.get('link', {}).get('repoId')
        deployment = _trigger_deployment(project_id, github_repo, repo_id, headers)
        if not deployment:
            raise Exception("Failed to trigger Vercel deployment")

        deployment_id = deployment.get('id')

        # Step 4: Wait for build to complete
        build_result = check_deployment_status(deployment_id, headers, max_wait_seconds=300)

        if not build_result['success']:
            # Build failed - include error details
            error_msg = build_result.get('error', 'Build failed')
            build_logs = build_result.get('build_logs', '')

            full_error = f"{error_msg}"
            if build_logs:
                full_error += f"\n\nBuild logs:\n{build_logs}"

            raise Exception(full_error)

        staging_url = f"https://{project_name}.vercel.app"
        production_url = f"https://{project_name}.darx.site"  # Custom domain (needs DNS)

        return {
            'success': True,
            'staging_url': staging_url,
            'production_url': production_url,
            'deployment_id': deployment_id,
            'build_state': build_result.get('state')
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def _get_or_create_project(project_name: str, github_repo: str, headers: Dict) -> Dict:
    """Get existing project or create new one"""

    # Try to get existing project
    url = f"https://api.vercel.com/v9/projects/{project_name}"
    if VERCEL_TEAM_ID:
        url += f"?teamId={VERCEL_TEAM_ID}"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()

    # Project doesn't exist, create it
    url = "https://api.vercel.com/v9/projects"
    if VERCEL_TEAM_ID:
        url += f"?teamId={VERCEL_TEAM_ID}"

    org, repo = github_repo.split('/')

    payload = {
        "name": project_name,
        "framework": "nextjs",
        "gitRepository": {
            "type": "github",
            "repo": github_repo
        },
        "buildCommand": "npm run build",
        "devCommand": "npm run dev",
        "installCommand": "npm install",
        "outputDirectory": ".next"
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in (200, 201):
        return response.json()
    else:
        print(f"Failed to create project: {response.text}")
        return None


def _set_env_vars(project_id: str, env_vars: Dict[str, str], headers: Dict):
    """Set environment variables for project"""

    url = f"https://api.vercel.com/v10/projects/{project_id}/env"
    if VERCEL_TEAM_ID:
        url += f"?teamId={VERCEL_TEAM_ID}"

    for key, value in env_vars.items():
        # Skip None values - Vercel API requires string values
        if value is None:
            print(f"   ⚠️  Skipping env var {key}: value is None")
            continue

        # Convert to string to ensure API compatibility
        value_str = str(value)

        payload = {
            "key": key,
            "value": value_str,
            "type": "encrypted",
            "target": ["production", "preview", "development"]
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code not in (200, 201):
            print(f"   ⚠️  Failed to set env var {key}: {response.text}")


def _trigger_deployment(project_id: str, github_repo: str, repo_id: int, headers: Dict) -> Dict:
    """Trigger a new deployment"""

    url = "https://api.vercel.com/v13/deployments"
    if VERCEL_TEAM_ID:
        url += f"?teamId={VERCEL_TEAM_ID}"

    payload = {
        "name": project_id,
        "gitSource": {
            "type": "github",
            "repo": github_repo,
            "repoId": repo_id,
            "ref": "main"
        },
        "target": "production"
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in (200, 201):
        return response.json()
    else:
        print(f"Failed to trigger deployment: {response.text}")
        return None


def check_deployment_status(deployment_id: str, headers: Dict, max_wait_seconds: int = 300) -> Dict[str, Any]:
    """
    Poll deployment status until it completes (success or error).

    Args:
        deployment_id: Vercel deployment ID
        headers: API headers with auth token
        max_wait_seconds: Maximum time to wait (default: 5 minutes)

    Returns:
        {
            'success': bool,
            'state': str (READY, ERROR, BUILDING, etc.),
            'error': str (if failed),
            'build_logs': str (if failed)
        }
    """
    import time

    url = f"https://api.vercel.com/v13/deployments/{deployment_id}"
    if VERCEL_TEAM_ID:
        url += f"?teamId={VERCEL_TEAM_ID}"

    start_time = time.time()
    poll_interval = 5  # Check every 5 seconds

    print(f"   Waiting for Vercel build to complete (deployment: {deployment_id})...")

    while True:
        elapsed = time.time() - start_time

        if elapsed > max_wait_seconds:
            return {
                'success': False,
                'state': 'TIMEOUT',
                'error': f'Build timed out after {max_wait_seconds} seconds'
            }

        # Get deployment status
        try:
            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                return {
                    'success': False,
                    'state': 'ERROR',
                    'error': f'Failed to check deployment status: {response.text}'
                }

            deployment = response.json()
            state = deployment.get('readyState', 'UNKNOWN')

            print(f"   Build status: {state} ({int(elapsed)}s elapsed)")

            # Check for completion states
            if state == 'READY':
                return {
                    'success': True,
                    'state': state,
                    'url': deployment.get('url')
                }

            elif state == 'ERROR':
                # Fetch build logs to get error details
                build_logs = _fetch_build_logs(deployment_id, headers)

                return {
                    'success': False,
                    'state': state,
                    'error': 'Build failed on Vercel',
                    'build_logs': build_logs
                }

            elif state == 'CANCELED':
                return {
                    'success': False,
                    'state': state,
                    'error': 'Build was canceled'
                }

            # Still building - wait and try again
            time.sleep(poll_interval)

        except Exception as e:
            return {
                'success': False,
                'state': 'ERROR',
                'error': f'Error checking deployment status: {str(e)}'
            }


def _fetch_build_logs(deployment_id: str, headers: Dict) -> str:
    """Fetch build logs for a failed deployment"""

    try:
        # Get deployment events/logs
        url = f"https://api.vercel.com/v2/deployments/{deployment_id}/events"
        if VERCEL_TEAM_ID:
            url += f"?teamId={VERCEL_TEAM_ID}"

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            return "Could not fetch build logs"

        events = response.json()

        # Extract error messages from events
        error_messages = []
        for event in events:
            if event.get('type') in ['stderr', 'error']:
                payload = event.get('payload', {})
                text = payload.get('text', '')
                if text:
                    error_messages.append(text)

        if error_messages:
            return '\n'.join(error_messages[-10:])  # Last 10 error messages
        else:
            return "Build failed but no error logs available"

    except Exception as e:
        return f"Error fetching logs: {str(e)}"
