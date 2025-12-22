"""
GCP operations: Cloud Storage and Supabase logging
"""

import os
import json
import zipfile
import io
from datetime import datetime
from google.cloud import storage
from typing import Dict, List, Any, Optional

# Import Supabase client from darx_core
from darx_core import get_supabase_client

# Configuration
PROJECT_ID = os.getenv('GCP_PROJECT', 'sylvan-journey-474401-f9')
BUCKET_NAME = os.getenv('GCS_BUCKET', 'darx-generated-sites')


def store_backup(
    project_name: str,
    files: List[Dict[str, str]],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Store generated code backup in Cloud Storage.

    Args:
        project_name: Project name
        files: List of {path, content} dicts
        metadata: Generation metadata (industry, features, etc.)

    Returns:
        {
            'success': bool,
            'backup_url': str,
            'error': str (if failed)
        }
    """

    try:
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file in files:
                zip_file.writestr(file['path'], file['content'])

            # Add metadata
            zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))

        zip_buffer.seek(0)

        # Upload to Cloud Storage
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)

        # Create blob path: projects/{project-name}/generation-{timestamp}.zip
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        blob_name = f"projects/{project_name}/generation-{timestamp}.zip"

        blob = bucket.blob(blob_name)
        blob.upload_from_file(zip_buffer, content_type='application/zip')

        # Make publicly readable (optional, remove if you want private)
        # blob.make_public()

        backup_url = f"gs://{BUCKET_NAME}/{blob_name}"

        print(f"   ✅ Backup stored: {backup_url}")

        return {
            'success': True,
            'backup_url': backup_url
        }

    except Exception as e:
        print(f"   ⚠️  Backup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def log_generation(
    project_name: str,
    industry: str,
    components: int,
    files: int,
    generation_time: float,
    success: bool,
    error: str = None,
    deployment_url: str = None,
    build_state: str = None,
    build_logs: str = None
):
    """
    Log generation metrics to Supabase and Cloud Logging.

    Args:
        project_name: Name of the generated project
        industry: Industry type (real-estate, saas, etc.)
        components: Number of components generated
        files: Number of files generated
        generation_time: Time taken to generate (seconds)
        success: Whether generation succeeded
        error: Error message if failed
        deployment_url: Vercel deployment URL
        build_state: Build state (READY, ERROR, etc.)
        build_logs: Build logs if failed
    """

    log_entry = {
        'created_at': datetime.utcnow().isoformat(),
        'project_name': project_name,
        'industry': industry,
        'components_generated': components,
        'files_generated': files,
        'generation_time_seconds': round(generation_time, 2),
        'success': success,
        'error_message': error,
        'deployment_url': deployment_url,
        'build_state': build_state,
        'build_logs': build_logs
    }

    # Log to stdout (captured by Cloud Logging)
    print(f"\n📊 Generation Metrics:")
    print(json.dumps(log_entry, indent=2))

    # Store in Supabase
    try:
        supabase = get_supabase_client()
        if supabase:
            supabase.table('darx_site_generations').insert(log_entry).execute()
            print("   ✅ Logged to Supabase")
        else:
            print("   ⚠️  Supabase not available, logged to Cloud Logging only")
    except Exception as e:
        print(f"   ⚠️  Failed to log to Supabase: {str(e)}")


def list_backups(client_slug: str) -> Dict[str, Any]:
    """
    List all GCS backups for a specific client.

    Args:
        client_slug: Client slug (e.g., 'acme-corp')

    Returns:
        {
            'success': bool,
            'backups': List[Dict],
            'count': int,
            'error': str (if failed)
        }
    """

    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)

        # List all blobs with prefix projects/{client_slug}/
        prefix = f"projects/{client_slug}/"
        blobs = bucket.list_blobs(prefix=prefix)

        backups = []
        for blob in blobs:
            backups.append({
                'name': blob.name,
                'size_bytes': blob.size,
                'created_at': blob.time_created.isoformat() if blob.time_created else None,
                'updated_at': blob.updated.isoformat() if blob.updated else None,
                'url': f"gs://{BUCKET_NAME}/{blob.name}",
                'public_url': blob.public_url if blob.public_url else None
            })

        # Sort by created_at descending (newest first)
        backups.sort(key=lambda x: x['created_at'] or '', reverse=True)

        return {
            'success': True,
            'backups': backups,
            'count': len(backups)
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to list backups: {str(e)}'
        }


def get_latest_backup(client_slug: str) -> Dict[str, Any]:
    """
    Get the most recent backup for a client.

    Args:
        client_slug: Client slug (e.g., 'acme-corp')

    Returns:
        {
            'success': bool,
            'backup': Dict,
            'error': str (if failed)
        }
    """

    try:
        result = list_backups(client_slug)

        if not result['success']:
            return result

        backups = result.get('backups', [])

        if not backups:
            return {
                'success': False,
                'error': f'No backups found for {client_slug}'
            }

        # Backups are already sorted by created_at descending
        latest = backups[0]

        return {
            'success': True,
            'backup': latest
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to get latest backup: {str(e)}'
        }


def delete_backups(client_slug: str, keep_latest: bool = True) -> Dict[str, Any]:
    """
    Delete GCS backups for a client.

    Args:
        client_slug: Client slug (e.g., 'acme-corp')
        keep_latest: If True, keeps the most recent backup for recovery (default: True)

    Returns:
        {
            'success': bool,
            'deleted_count': int,
            'kept_backup': str (if keep_latest=True),
            'error': str (if failed)
        }
    """

    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)

        # List all backups
        result = list_backups(client_slug)

        if not result['success']:
            return result

        backups = result.get('backups', [])

        if not backups:
            return {
                'success': True,
                'deleted_count': 0,
                'note': f'No backups found for {client_slug}'
            }

        # Determine which backups to delete
        backups_to_delete = backups[1:] if keep_latest else backups
        kept_backup = backups[0]['name'] if keep_latest and backups else None

        deleted_count = 0
        errors = []

        for backup in backups_to_delete:
            try:
                blob = bucket.blob(backup['name'])
                blob.delete()
                deleted_count += 1
            except Exception as e:
                errors.append(f"Failed to delete {backup['name']}: {str(e)}")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'kept_backup': kept_backup,
            'errors': errors if errors else None
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to delete backups: {str(e)}'
        }
