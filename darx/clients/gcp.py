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
from supabase import create_client, Client

# Configuration
PROJECT_ID = os.getenv('GCP_PROJECT', 'sylvan-journey-474401-f9')
BUCKET_NAME = os.getenv('GCS_BUCKET', 'darx-generated-sites')

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Global Supabase client
_supabase_client = None


def get_supabase_client() -> Optional[Client]:
    """Get or create Supabase client"""
    global _supabase_client

    if _supabase_client is None:
        if SUPABASE_URL and SUPABASE_KEY:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        else:
            print("⚠️  Supabase not configured (SUPABASE_URL or SUPABASE_KEY missing)")

    return _supabase_client


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
