"""
GitHub operations for repository creation and code pushing
"""

import os
import base64
from github import Github, GithubException, Auth, InputGitTreeElement
from typing import Dict, List, Any

# GitHub App credentials
GITHUB_APP_ID = os.getenv('GITHUB_APP_ID')
GITHUB_APP_PRIVATE_KEY = os.getenv('GITHUB_APP_PRIVATE_KEY')
GITHUB_APP_INSTALLATION_ID = os.getenv('GITHUB_APP_INSTALLATION_ID')

_github_client = None


def get_github_client():
    """Get authenticated GitHub client using GitHub App"""
    global _github_client

    if _github_client is not None:
        return _github_client

    if not all([GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_INSTALLATION_ID]):
        raise Exception(
            "GitHub App not configured. Need: GITHUB_APP_ID, "
            "GITHUB_APP_PRIVATE_KEY, GITHUB_APP_INSTALLATION_ID"
        )

    try:
        # Authenticate as GitHub App installation
        auth = Auth.AppAuth(
            app_id=int(GITHUB_APP_ID),
            private_key=GITHUB_APP_PRIVATE_KEY
        )

        # Get installation token
        gi = auth.get_installation_auth(int(GITHUB_APP_INSTALLATION_ID))

        # Create GitHub client with installation token
        _github_client = Github(auth=gi)

        return _github_client

    except Exception as e:
        raise Exception(f"Failed to authenticate with GitHub App: {str(e)}")


def create_github_repo(
    org: str,
    repo_name: str,
    description: str = "",
    private: bool = False
) -> Dict[str, Any]:
    """
    Create a new GitHub repository.

    Args:
        org: Organization name (e.g., 'darx-sites')
        repo_name: Repository name (e.g., 'acme-corp')
        description: Repository description
        private: Whether repository should be private

    Returns:
        {
            'success': bool,
            'repo_url': str,
            'error': str (if failed)
        }
    """

    try:
        github = get_github_client()

        # Get organization
        try:
            organization = github.get_organization(org)
        except GithubException:
            # If org doesn't exist, create repo in user's account
            user = github.get_user()
            repo = user.create_repo(
                name=repo_name,
                description=description,
                private=private,
                auto_init=True  # Initialize with README to avoid empty repo issues
            )
            return {
                'success': True,
                'repo_url': repo.html_url
            }

        # Create repository in organization
        repo = organization.create_repo(
            name=repo_name,
            description=description,
            private=private,
            auto_init=True,  # Initialize with README to avoid empty repo issues
            has_issues=True,
            has_wiki=False,
            has_projects=True
        )

        return {
            'success': True,
            'repo_url': repo.html_url
        }

    except GithubException as e:
        if e.status == 422 and 'already exists' in str(e):
            # Repository already exists, return existing URL
            try:
                repo = github.get_repo(f"{org}/{repo_name}")
                return {
                    'success': True,
                    'repo_url': repo.html_url,
                    'note': 'Repository already existed'
                }
            except:
                pass

        return {
            'success': False,
            'error': f'GitHub API error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def push_to_github(
    org: str,
    repo_name: str,
    files: List[Dict[str, str]],
    commit_message: str = "Initial commit",
    branch: str = "main"
) -> Dict[str, Any]:
    """
    Push files to GitHub repository.

    Args:
        org: Organization name
        repo_name: Repository name
        files: List of {path, content} dicts
        commit_message: Commit message
        branch: Branch name (default: main)

    Returns:
        {
            'success': bool,
            'commit_sha': str,
            'error': str (if failed)
        }
    """

    try:
        github = get_github_client()
        repo = github.get_repo(f"{org}/{repo_name}")

        # Get or create branch
        # Repository is now always initialized with README, so default branch exists
        try:
            # Try to get the specified branch
            ref = repo.get_git_ref(f"heads/{branch}")
            base_sha = ref.object.sha
        except GithubException:
            # Branch doesn't exist, create from default branch
            default_branch = repo.default_branch
            default_ref = repo.get_git_ref(f"heads/{default_branch}")
            base_sha = default_ref.object.sha

            # Create new branch
            repo.create_git_ref(f"refs/heads/{branch}", base_sha)
            ref = repo.get_git_ref(f"heads/{branch}")

        # Get base tree and parent commit
        parent_commit = repo.get_git_commit(base_sha)
        base_tree = parent_commit.tree

        # Create tree with all files
        tree_elements = []
        for file in files:
            # Encode content to base64
            content = file['content']
            if isinstance(content, str):
                content = content.encode('utf-8')

            blob = repo.create_git_blob(
                base64.b64encode(content).decode('utf-8'),
                encoding='base64'
            )

            element = InputGitTreeElement(
                path=file['path'],
                mode='100644',  # Regular file
                type='blob',
                sha=blob.sha
            )
            tree_elements.append(element)

        # Create tree
        tree = repo.create_git_tree(tree=tree_elements, base_tree=base_tree)

        # Create commit
        commit = repo.create_git_commit(
            message=commit_message,
            tree=tree,
            parents=[parent_commit]
        )

        # Update branch reference
        ref.edit(commit.sha)

        return {
            'success': True,
            'commit_sha': commit.sha
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to push to GitHub: {str(e)}'
        }


def get_file_content(
    org: str,
    repo_name: str,
    file_path: str,
    branch: str = "main"
) -> Dict[str, Any]:
    """
    Get the content of a file from GitHub.

    Args:
        org: Organization name
        repo_name: Repository name
        file_path: Path to file (e.g., 'app/page.tsx')
        branch: Branch name (default: main)

    Returns:
        {
            'success': bool,
            'content': str,
            'sha': str (needed for updates),
            'error': str (if failed)
        }
    """

    try:
        github = get_github_client()
        repo = github.get_repo(f"{org}/{repo_name}")

        # Get file content
        file_content = repo.get_contents(file_path, ref=branch)

        # Decode base64 content
        content = base64.b64decode(file_content.content).decode('utf-8')

        return {
            'success': True,
            'content': content,
            'sha': file_content.sha
        }

    except GithubException as e:
        if e.status == 404:
            return {
                'success': False,
                'error': f'File not found: {file_path}'
            }
        return {
            'success': False,
            'error': f'GitHub API error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def update_file_content(
    org: str,
    repo_name: str,
    file_path: str,
    content: str,
    sha: str,
    commit_message: str = "Update file",
    branch: str = "main"
) -> Dict[str, Any]:
    """
    Update a file in GitHub repository.

    Args:
        org: Organization name
        repo_name: Repository name
        file_path: Path to file
        content: New file content
        sha: SHA of file being replaced (from get_file_content)
        commit_message: Commit message
        branch: Branch name (default: main)

    Returns:
        {
            'success': bool,
            'commit_sha': str,
            'error': str (if failed)
        }
    """

    try:
        github = get_github_client()
        repo = github.get_repo(f"{org}/{repo_name}")

        # Update file
        result = repo.update_file(
            path=file_path,
            message=commit_message,
            content=content,
            sha=sha,
            branch=branch
        )

        return {
            'success': True,
            'commit_sha': result['commit'].sha
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to update file: {str(e)}'
        }
