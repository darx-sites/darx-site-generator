"""
Site Editor - Make targeted edits to existing DARX Sites
"""

import os
from typing import Dict, List, Any
from .github import get_file_content, update_file_content
from .vertex_ai import get_client


def edit_site(
    project_name: str,
    edit_type: str,
    changes: Dict[str, Any],
    github_org: str = 'darx-sites'
) -> Dict[str, Any]:
    """
    Make targeted edits to an existing DARX Site.

    Args:
        project_name: Project name (e.g., 'food-asmr-hub')
        edit_type: Type of edit ('color_palette', 'content', 'typography', 'layout', 'animation', 'add_section')
        changes: Edit-specific parameters
        github_org: GitHub organization (default: 'darx-sites')

    Returns:
        {
            'success': bool,
            'files_updated': list,
            'commit_sha': str,
            'staging_url': str,
            'error': str (if failed)
        }
    """

    try:
        print(f"\n✏️  Editing {project_name}: {edit_type}")

        # Step 1: Determine which files need to be updated
        files_to_update = _determine_files_for_edit_type(edit_type)
        print(f"   Files to update: {', '.join(files_to_update)}")

        # Step 2: Fetch current file contents from GitHub
        current_files = {}
        for file_path in files_to_update:
            content_result = get_file_content(
                org=github_org,
                repo_name=project_name,
                file_path=file_path
            )
            if content_result.get('success'):
                current_files[file_path] = {
                    'content': content_result['content'],
                    'sha': content_result['sha']
                }
            else:
                print(f"   ⚠️  Could not fetch {file_path}: {content_result.get('error')}")

        if not current_files:
            return {
                'success': False,
                'error': 'Could not fetch any files from repository'
            }

        # Step 3: Generate edited code using Claude
        print("   Generating edited code with Claude...")
        edited_files = _generate_edits(
            edit_type=edit_type,
            changes=changes,
            current_files=current_files
        )

        if not edited_files.get('success'):
            return {
                'success': False,
                'error': edited_files.get('error', 'Code generation failed')
            }

        # Step 4: Update files in GitHub
        print("   Pushing changes to GitHub...")
        updated_files = []
        for file_path, new_content in edited_files['files'].items():
            if file_path in current_files:
                update_result = update_file_content(
                    org=github_org,
                    repo_name=project_name,
                    file_path=file_path,
                    content=new_content,
                    sha=current_files[file_path]['sha'],
                    commit_message=f"Edit: {edit_type}\n\nUpdated via DARX AI"
                )

                if update_result.get('success'):
                    updated_files.append(file_path)
                    print(f"   ✅ Updated {file_path}")
                else:
                    print(f"   ❌ Failed to update {file_path}: {update_result.get('error')}")

        if not updated_files:
            return {
                'success': False,
                'error': 'Failed to update any files in GitHub'
            }

        # Step 5: Vercel will automatically redeploy on push
        staging_url = f"https://{project_name}.vercel.app"

        print(f"   ✅ Edit complete! Vercel deploying to {staging_url}")

        return {
            'success': True,
            'files_updated': updated_files,
            'staging_url': staging_url,
            'edit_type': edit_type,
            'changes_applied': changes
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Site edit error: {str(e)}'
        }


def _determine_files_for_edit_type(edit_type: str) -> List[str]:
    """Determine which files need to be updated for each edit type"""

    file_map = {
        'color_palette': ['tailwind.config.ts', 'app/globals.css'],
        'content': ['app/page.tsx'],
        'typography': ['tailwind.config.ts', 'app/globals.css'],
        'layout': ['app/page.tsx', 'tailwind.config.ts'],
        'animation': ['app/page.tsx'],
        'add_section': ['app/page.tsx'],
        'fix_bug': ['app/page.tsx'],  # May need other files too
        'update_images': ['app/page.tsx'],
        'seo': ['app/layout.tsx']
    }

    return file_map.get(edit_type, ['app/page.tsx'])


def _generate_edits(
    edit_type: str,
    changes: Dict[str, Any],
    current_files: Dict[str, Dict]
) -> Dict[str, Any]:
    """
    Use Claude to generate edited versions of files.

    Args:
        edit_type: Type of edit being made
        changes: Specific changes requested
        current_files: Dict of {file_path: {'content': str, 'sha': str}}

    Returns:
        {
            'success': bool,
            'files': {file_path: new_content},
            'error': str (if failed)
        }
    """

    try:
        # Build prompt based on edit type
        prompt = _build_edit_prompt(edit_type, changes, current_files)

        client = get_client()
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=16384,
            temperature=0.1,
            system="""You are a code editor for Next.js websites. You make precise, targeted edits while preserving all existing functionality.

CRITICAL RULES:
1. ONLY modify what was requested - preserve everything else exactly
2. Maintain all existing imports, components, and structure
3. Keep TypeScript types correct
4. Preserve Tailwind CSS classes unless specifically changing design
5. Don't add comments explaining changes
6. Return ONLY the complete, updated file contents

OUTPUT FORMAT:
Return a JSON object with updated file contents:
{
  "files": {
    "app/page.tsx": "complete updated file content",
    "tailwind.config.ts": "complete updated file content"
  }
}

Use proper JSON escaping for quotes and newlines.""",
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        response_text = response.content[0].text

        # Parse JSON response
        import json

        # Extract JSON from markdown blocks if present
        if '```json' in response_text:
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            response_text = response_text[start:end].strip()
        elif '```' in response_text:
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            response_text = response_text[start:end].strip()

        result = json.loads(response_text)

        if 'files' not in result:
            raise Exception("No 'files' key in response")

        return {
            'success': True,
            'files': result['files']
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Code generation failed: {str(e)}'
        }


def _build_edit_prompt(
    edit_type: str,
    changes: Dict[str, Any],
    current_files: Dict[str, Dict]
) -> str:
    """Build the prompt for Claude based on edit type"""

    # Start with current file contents
    prompt_parts = ["# Current Files\n"]

    for file_path, file_data in current_files.items():
        prompt_parts.append(f"## {file_path}")
        prompt_parts.append("```typescript")
        prompt_parts.append(file_data['content'])
        prompt_parts.append("```\n")

    # Add edit-specific instructions
    prompt_parts.append(f"\n# Edit Request: {edit_type}\n")

    if edit_type == 'color_palette':
        prompt_parts.append(f"""Update the color palette to match these specifications:
- Primary: {changes.get('primary', 'keep current')}
- Secondary: {changes.get('secondary', 'keep current')}
- Accent: {changes.get('accent', 'keep current')}
- Background: {changes.get('background', 'keep current')}
- Text: {changes.get('text', 'keep current')}

Update both tailwind.config.ts theme colors and any hardcoded colors in CSS.
Replace all instances of the old colors with the new ones.""")

    elif edit_type == 'content':
        prompt_parts.append(f"""Update the content as specified:
{changes.get('instructions', '')}

File to update: {changes.get('file', 'app/page.tsx')}
Section: {changes.get('section', 'specified in instructions')}
New content: {changes.get('new_content', 'specified in instructions')}

Preserve all styling, structure, and other content.""")

    elif edit_type == 'typography':
        prompt_parts.append(f"""Update typography settings:
- Heading font: {changes.get('heading_font', 'keep current')}
- Body font: {changes.get('body_font', 'keep current')}
- Font sizes: {changes.get('type_scale', 'keep current')}

Update tailwind.config.ts fontFamily and fontSize.
Update @import statements in globals.css if changing Google Fonts.""")

    elif edit_type == 'layout':
        prompt_parts.append(f"""Adjust layout:
{changes.get('instructions', '')}

Spacing: {changes.get('spacing', 'keep current')}
Grid: {changes.get('grid', 'keep current')}
Max width: {changes.get('max_width', 'keep current')}

Update Tailwind spacing classes in components.""")

    elif edit_type == 'animation':
        prompt_parts.append(f"""Update animations:
{changes.get('instructions', '')}

Animation style: {changes.get('style', 'keep current')}
Duration: {changes.get('duration', 'keep current')}
Easing: {changes.get('easing', 'keep current')}

Update Framer Motion variants and transition settings.""")

    elif edit_type == 'add_section':
        prompt_parts.append(f"""Add a new section to the page:
Component: {changes.get('component_type', 'generic section')}
Position: {changes.get('position', 'at the end')}
Content: {changes.get('content', 'to be specified')}

Add the new section component inline in app/page.tsx.
Match the existing design system (colors, typography, spacing).""")

    elif edit_type == 'fix_bug':
        prompt_parts.append(f"""Fix the following bug:
{changes.get('bug_description', '')}

Expected behavior: {changes.get('expected', '')}
Current behavior: {changes.get('actual', '')}

Fix the bug while preserving all other functionality.""")

    else:
        # Generic edit
        prompt_parts.append(f"""Make the following changes:
{changes.get('instructions', '')}

Follow the specifications exactly.""")

    prompt_parts.append("\nReturn the complete updated file contents in JSON format.")

    return '\n'.join(prompt_parts)
