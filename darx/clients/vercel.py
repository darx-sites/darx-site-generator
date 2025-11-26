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

        # Wait a moment for URL to be available
        import time
        time.sleep(2)

        staging_url = f"https://{project_name}.vercel.app"
        production_url = f"https://{project_name}.darx.site"  # Custom domain (needs DNS)

        return {
            'success': True,
            'staging_url': staging_url,
            'production_url': production_url,
            'deployment_id': deployment.get('id')
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
        payload = {
            "key": key,
            "value": value,
            "type": "encrypted",
            "target": ["production", "preview", "development"]
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code not in (200, 201):
            print(f"Warning: Failed to set env var {key}: {response.text}")


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
        "target": "preview"
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in (200, 201):
        return response.json()
    else:
        print(f"Failed to trigger deployment: {response.text}")
        return None
