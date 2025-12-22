#!/usr/bin/env python3
"""
Script to delete test-client-10 GitHub repo and Vercel project
"""

import os
import requests
from github import Github, GithubException, Auth

# Load environment variables
GITHUB_APP_ID = os.getenv('GITHUB_APP_ID')
GITHUB_APP_PRIVATE_KEY = os.getenv('GITHUB_APP_PRIVATE_KEY')
GITHUB_APP_INSTALLATION_ID = os.getenv('GITHUB_APP_INSTALLATION_ID')
VERCEL_TOKEN = os.getenv('VERCEL_TOKEN')
VERCEL_TEAM_ID = os.getenv('VERCEL_TEAM_ID')


def get_github_client():
    """Get authenticated GitHub client using GitHub App"""
    if not all([GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_INSTALLATION_ID]):
        raise Exception("GitHub App not configured")

    auth = Auth.AppAuth(
        app_id=int(GITHUB_APP_ID),
        private_key=GITHUB_APP_PRIVATE_KEY
    )
    gi = auth.get_installation_auth(int(GITHUB_APP_INSTALLATION_ID))
    return Github(auth=gi)


def delete_github_repo(org: str, repo_name: str):
    """Delete a GitHub repository"""
    try:
        github = get_github_client()
        repo = github.get_repo(f"{org}/{repo_name}")
        repo.delete()
        return {'success': True, 'repo': f"{org}/{repo_name}"}
    except GithubException as e:
        if e.status == 404:
            return {'success': False, 'error': f'Repository not found: {org}/{repo_name}'}
        return {'success': False, 'error': f'GitHub API error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def delete_vercel_project(project_id: str):
    """Delete a Vercel project"""
    if not VERCEL_TOKEN:
        return {
            'success': False,
            'error': 'VERCEL_TOKEN not configured'
        }

    headers = {
        'Authorization': f'Bearer {VERCEL_TOKEN}',
        'Content-Type': 'application/json'
    }

    url = f"https://api.vercel.com/v9/projects/{project_id}"
    if VERCEL_TEAM_ID:
        url += f"?teamId={VERCEL_TEAM_ID}"

    response = requests.delete(url, headers=headers)

    if response.status_code in (200, 204):
        return {'success': True, 'project_id': project_id}
    elif response.status_code == 404:
        return {'success': True, 'project_id': project_id, 'note': 'Project not found (already deleted)'}
    else:
        return {
            'success': False,
            'error': f'Failed to delete project: {response.status_code} - {response.text}'
        }


if __name__ == '__main__':
    print("Deleting test-client-10...")
    print()

    # Delete GitHub repo
    print("1. Deleting GitHub repo darx-sites/test-client-10...")
    github_result = delete_github_repo('darx-sites', 'test-client-10')
    if github_result['success']:
        print(f"   ✅ GitHub repo deleted: {github_result['repo']}")
    else:
        print(f"   ❌ GitHub error: {github_result['error']}")
    print()

    # Delete Vercel project
    print("2. Deleting Vercel project test-client-10...")
    vercel_result = delete_vercel_project('test-client-10')
    if vercel_result['success']:
        note = vercel_result.get('note', '')
        print(f"   ✅ Vercel project deleted: {vercel_result['project_id']} {note}")
    else:
        print(f"   ❌ Vercel error: {vercel_result['error']}")
    print()

    print("Done!")
