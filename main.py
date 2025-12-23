"""
DARX Site Generator - Cloud Run Service

Generates production-ready Next.js websites with Builder.io integration.
"""

import os
import json
import time
import requests
import secrets
from flask import Flask, request, jsonify
from flask_session import Session
from typing import Dict, Any
from darx.clients.vertex_ai import generate_site_code
from darx.clients.github import create_github_repo, push_to_github
from darx.clients.vercel import deploy_to_vercel
from darx.clients.site_editor import edit_site
from darx.clients.gcp import store_backup, log_generation
from onboarding import onboarding_bp
from auth import init_oauth
from auth_routes import auth_bp, init_auth_routes
from google.cloud import secretmanager, pubsub_v1

# Initialize structured logging from darx_core
from darx_core import setup_logging, get_logger
logger = setup_logging('darx-site-generator', log_level=os.environ.get('LOG_LEVEL', 'INFO'))

# Configuration
PROJECT_ID = os.getenv('GCP_PROJECT', 'sylvan-journey-474401-f9')


def _generate_error_help(error_type: str, error_msg: str) -> Dict:
    """
    Generate contextual help based on error type.
    """
    if 'Vercel' in error_msg:
        return {
            'message': 'Vercel deployment or API error',
            'next_steps': [
                'Check Vercel API token is valid',
                'Verify project permissions',
                'Review Vercel deployment logs'
            ]
        }

    elif 'Builder.io' in error_msg or 'BuilderIO' in error_msg:
        return {
            'message': 'Builder.io API error',
            'next_steps': [
                'Check Builder.io API key is valid',
                'Verify space permissions',
                'Check Builder.io space quotas'
            ]
        }

    elif 'GitHub' in error_msg:
        return {
            'message': 'GitHub API error',
            'next_steps': [
                'Check GitHub token is valid',
                'Verify repository permissions',
                'Check rate limits'
            ]
        }

    return {
        'message': 'Unexpected error during site generation',
        'next_steps': [
            'Review error logs',
            'Check service configurations',
            'Contact support if error persists'
        ]
    }


def get_builder_keys_from_secret_manager(project_id: str, secret_prefix: str = '') -> Dict[str, str]:
    """
    Retrieve Builder.io keys from Secret Manager

    Args:
        project_id: GCP project containing the secrets
        secret_prefix: Prefix for secret names (e.g., 'client-slug-' for INTAKE mode)

    Returns:
        {'public_key': '...', 'private_key': '...'}
    """
    secret_client = secretmanager.SecretManagerServiceClient()

    try:
        # Retrieve public key
        public_key_name = f"projects/{project_id}/secrets/{secret_prefix}builder-public-key/versions/latest"
        public_key_response = secret_client.access_secret_version(name=public_key_name)
        public_key = public_key_response.payload.data.decode('UTF-8')

        # Retrieve private key
        private_key_name = f"projects/{project_id}/secrets/{secret_prefix}builder-private-key/versions/latest"
        private_key_response = secret_client.access_secret_version(name=private_key_name)
        private_key = private_key_response.payload.data.decode('UTF-8')

        print(f"   ✅ Retrieved Builder.io keys from Secret Manager")
        print(f"   ℹ️  Project: {project_id}, Prefix: {secret_prefix}")

        return {
            'public_key': public_key,
            'private_key': private_key
        }

    except Exception as e:
        print(f"   ⚠️  Failed to retrieve Builder.io keys from Secret Manager: {str(e)}")
        return {'public_key': None, 'private_key': None}


LOCATION = os.getenv('GCP_LOCATION', 'us-central1')
GITHUB_ORG = os.getenv('GITHUB_ORG', 'darx-sites')
DARX_REASONING_URL = os.getenv('DARX_REASONING_URL', 'https://darx-reasoning-474964350921.us-central1.run.app')


def _configure_builder_preview_url(
    staging_url: str,
    builder_public_key: str,
    builder_private_key: str,
    model_name: str = 'page'
) -> None:
    """
    Configure Builder.io model preview URL to enable visual editing

    This sets the staging URL as the preview URL so Builder.io can iframe/preview the deployed site.

    Args:
        staging_url: URL of the deployed Vercel site
        builder_public_key: Builder.io public API key
        builder_private_key: Builder.io private API key
        model_name: Model to configure (default: 'page')
    """
    if not builder_public_key or not builder_private_key:
        print(f"   ⚠️  Builder.io keys not available - skipping preview URL configuration")
        return

    try:
        # Check if model exists
        check_url = f"https://cdn.builder.io/api/v1/models/{model_name}?apiKey={builder_public_key}"
        check_response = requests.get(check_url, timeout=30)

        if check_response.status_code == 404:
            # Model doesn't exist - create it
            print(f"   📝 Creating '{model_name}' model with preview URL...")

            create_url = "https://builder.io/api/v1/models"
            headers = {
                'Authorization': f'Bearer {builder_private_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'name': model_name.title(),
                'id': model_name,
                'kind': 'page',
                'examplePageUrl': staging_url,
                'publicReadable': True,
                'showTargeting': True,
                'showMetrics': True,
                'allowHeatmap': True
            }

            create_response = requests.post(
                create_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            create_response.raise_for_status()
            print(f"   ✅ Created '{model_name}' model with preview URL: {staging_url}")

        else:
            # Model exists - update preview URL
            check_response.raise_for_status()
            model_data = check_response.json()

            current_preview_url = model_data.get('examplePageUrl')
            print(f"   ℹ️  Current preview URL: {current_preview_url or 'Not set'}")

            # Update the model with the preview URL
            update_url = f"https://builder.io/api/v1/models/{model_name}"
            headers = {
                'Authorization': f'Bearer {builder_private_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'examplePageUrl': staging_url
            }

            update_response = requests.put(
                update_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            update_response.raise_for_status()
            print(f"   ✅ Updated '{model_name}' model preview URL: {staging_url}")

    except requests.exceptions.HTTPError as e:
        error_msg = f"{e.response.status_code} - {e.response.text if hasattr(e, 'response') else str(e)}"
        print(f"   ⚠️  Builder.io API error: {error_msg}")
        raise
    except Exception as e:
        print(f"   ⚠️  Failed to configure preview URL: {str(e)}")
        raise


# Create Flask app
app = Flask(__name__)

# Session configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True  # Require HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
Session(app)

# Initialize OAuth
oauth, google = init_oauth(app)
init_auth_routes(google)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(onboarding_bp)


@app.route('/', methods=['POST', 'OPTIONS'])
def generate_site():
    """
    Main HTTP endpoint for website generation.

    Request body:
    {
        "project_name": "acme-corp",
        "client_info": {...},
        "requirements": "Build a landing page...",
        "industry": "real-estate",
        "features": ["spline-3d", "hubspot-form"],
        "builder_space_public_key": "pub-..." (optional - use existing Builder.io Space)
    }

    Returns:
    {
        "success": true,
        "staging_url": "https://staging.acme-corp.darx.site",
        "github_repo": "https://github.com/darx-sites/acme-corp",
        "builder_io_project": "acme-corp",
        "components_registered": [...]
    }
    """

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return _cors_response()

    # Parse request
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        project_name = data.get('project_name')
        client_info = data.get('client_info', {})
        requirements = data.get('requirements')
        industry = data.get('industry', 'general')
        features = data.get('features', [])
        builder_space_public_key = data.get('builder_space_public_key')  # Optional: use existing Builder.io Space

        # INTAKE mode support
        mode = data.get('mode', 'DEDICATED')  # 'INTAKE' or 'DEDICATED'
        gcp_project_id = data.get('gcp_project_id')  # Where to retrieve secrets from
        secret_prefix = data.get('secret_prefix', '')  # Prefix for secret names (e.g., 'client-slug-')

        if not project_name or not requirements:
            return jsonify({
                'error': 'Missing required fields: project_name, requirements'
            }), 400

    except Exception as e:
        return jsonify({'error': f'Invalid request: {str(e)}'}), 400

    # CRITICAL FIX: Workflow validation (Fix #4)
    # Check if client exists and is active before allowing site generation
    try:
        from darx_core import get_supabase_client
        supabase = get_supabase_client()

        if supabase:
            # Query for client record using client_slug (which is project_name)
            client_check = supabase.table('clients')\
                .select('client_slug, name, status, onboarding_completed')\
                .eq('client_slug', project_name)\
                .execute()

            if not client_check.data or len(client_check.data) == 0:
                return jsonify({
                    'error': 'Client not found',
                    'message': f'No client record found for slug: {project_name}',
                    'recommendation': 'Please onboard the client first using the client_onboarding tool',
                    'required_step': 'onboard_client',
                    'blocked': True
                }), 400

            client_record = client_check.data[0]

            # Check if client is in active status
            if client_record.get('status') != 'active':
                current_status = client_record.get('status', 'unknown')
                return jsonify({
                    'error': 'Client not ready for site generation',
                    'message': f'Client status is "{current_status}" (expected "active")',
                    'current_status': current_status,
                    'client_slug': project_name,
                    'recommendation': {
                        'pending_provisioning': 'Wait for provisioning workflow to complete',
                        'pending_onboarding': 'Complete onboarding first',
                        'inactive': 'Client has been deactivated',
                        'unknown': 'Check client status in Supabase'
                    }.get(current_status, 'Contact support'),
                    'blocked': True
                }), 400

            print(f"✅ Client validation passed: {project_name} (status: active)")

    except Exception as e:
        print(f"⚠️  Client validation check failed: {e}")
        # Continue anyway if validation fails - this is a safety feature, not critical
        # But log the warning so we know validation isn't working

    print(f"\n🚀 Starting generation for: {project_name}")
    print(f"   Industry: {industry}")
    print(f"   Features: {', '.join(features)}")

    start_time = time.time()

    try:
        # Step 1: Generate code with Claude
        print("\n📝 Generating code with Claude Sonnet 4.5...")
        generation_result = generate_site_code(
            project_name=project_name,
            requirements=requirements,
            industry=industry,
            features=features,
            client_info=client_info
        )

        if not generation_result.get('success'):
            raise Exception(generation_result.get('error', 'Code generation failed'))

        files = generation_result['files']
        components = generation_result['components']

        print(f"   ✅ Generated {len(files)} files")
        print(f"   ✅ Registered {len(components)} components")

        # Step 2: Create GitHub repository
        print(f"\n📦 Creating GitHub repository: {GITHUB_ORG}/{project_name}")
        github_result = create_github_repo(
            org=GITHUB_ORG,
            repo_name=project_name,
            description=f"Website for {client_info.get('client_name', project_name)}"
        )

        if not github_result.get('success'):
            raise Exception(github_result.get('error', 'GitHub repo creation failed'))

        repo_url = github_result['repo_url']
        print(f"   ✅ Repository created: {repo_url}")

        # Step 3: Push code to GitHub
        print("\n⬆️  Pushing code to GitHub...")
        push_result = push_to_github(
            org=GITHUB_ORG,
            repo_name=project_name,
            files=files,
            commit_message=f"Initial commit - Generated by DARX\n\nIndustry: {industry}\nComponents: {len(components)}"
        )

        if not push_result.get('success'):
            raise Exception(push_result.get('error', 'GitHub push failed'))

        print("   ✅ Code pushed to GitHub")

        # Step 4: Retrieve Builder.io keys (from Secret Manager or env vars)
        print("\n🔑 Retrieving Builder.io credentials...")
        if mode == 'INTAKE' and gcp_project_id:
            # INTAKE mode: Retrieve from shared project's Secret Manager
            builder_keys = get_builder_keys_from_secret_manager(gcp_project_id, secret_prefix)
            builder_public_key_for_env = builder_keys.get('public_key')
            builder_private_key_for_env = builder_keys.get('private_key')
        else:
            # DEDICATED mode or fallback: Use environment variables
            builder_public_key_for_env = os.getenv('BUILDER_IO_PUBLIC_KEY')
            builder_private_key_for_env = os.getenv('BUILDER_IO_PRIVATE_KEY')
            print(f"   ℹ️  Using environment variables for Builder.io keys")

        # Step 5: Deploy to Vercel
        print("\n🚀 Deploying to Vercel...")

        # Determine Builder.io space mode based on provisioning mode
        builder_space_mode = 'SHARED' if mode == 'INTAKE' else 'DEDICATED'
        print(f"   ℹ️  Builder.io space mode: {builder_space_mode}")

        vercel_result = deploy_to_vercel(
            project_name=project_name,
            github_repo=f"{GITHUB_ORG}/{project_name}",
            env_vars={
                'NEXT_PUBLIC_BUILDER_API_KEY': builder_public_key_for_env,
                'BUILDER_PRIVATE_KEY': builder_private_key_for_env,
                'BUILDER_SPACE_MODE': builder_space_mode,
                'NEXT_PUBLIC_CLIENT_SLUG': project_name,  # Required for SHARED space client slug
                'NEXT_PUBLIC_BUILDER_SPACE_MODE': builder_space_mode,  # Client-side access to space mode
            }
        )

        if not vercel_result.get('success'):
            raise Exception(vercel_result.get('error', 'Vercel deployment failed'))

        staging_url = vercel_result['staging_url']
        print(f"   ✅ Deployed to: {staging_url}")

        # Step 5.5: Configure Builder.io preview URL for visual editing
        print("\n🔧 Configuring Builder.io preview URL...")
        try:
            # Use correct model name based on space mode
            preview_model_name = 'client-page' if builder_space_mode == 'SHARED' else 'page'
            _configure_builder_preview_url(
                staging_url=staging_url,
                builder_public_key=builder_public_key_for_env,
                builder_private_key=builder_private_key_for_env,
                model_name=preview_model_name
            )
        except Exception as e:
            print(f"   ⚠️  Failed to configure preview URL: {str(e)}")
            print(f"   ℹ️  Visual editing may not work properly")

        # Step 6: Configure Builder.io visual editor
        print("\n🎨 Setting up Builder.io visual editor...")
        builder_space_id = project_name  # Default fallback
        builder_public_key = builder_public_key_for_env  # Use retrieved keys
        builder_private_key = builder_private_key_for_env  # Use retrieved keys
        builder_space_url = None

        if builder_space_public_key:
            # User provided an existing Builder.io Space key - use it directly
            print(f"   ✅ Using existing Builder.io Space")
            print(f"   ℹ️  Public key: {builder_space_public_key[:20]}...")
            builder_public_key = builder_space_public_key
            builder_space_id = project_name
            builder_space_url = f"https://builder.io/content"
            print(f"   ℹ️  Visual editing will be available with your existing Space")
        else:
            # No key provided - attempt to create a new Space (requires Enterprise account)
            try:
                from darx.clients.builderio_space import create_space

                space_name = client_info.get('client_name') or project_name.replace('-', ' ').title()

                builder_result = create_space(
                    space_name=space_name,
                    vercel_project_id=vercel_result.get('vercel_project_id')
                )

                if builder_result.get('success'):
                    builder_space_id = builder_result.get('space_id', project_name)
                    builder_public_key = builder_result.get('public_key')
                    builder_private_key = builder_result.get('private_key')
                    builder_space_url = builder_result.get('space_url')

                    print(f"   ✅ Builder.io space created: {builder_space_id}")
                    print(f"   ℹ️  Public key: {builder_public_key}")
                    print(f"   ℹ️  Space URL: {builder_space_url}")
                else:
                    error_msg = builder_result.get('error', 'Unknown error')
                    print(f"   ⚠️  Builder.io Space creation failed: {error_msg}")
                    # Check if this is the Enterprise limitation
                    if '401' in error_msg or 'Invalid key' in error_msg or 'Unauthorized' in error_msg:
                        print(f"   ℹ️  NOTE: Programmatic Space creation requires a Builder.io Enterprise account.")
                        print(f"   ℹ️  To enable visual editing, create a Space at builder.io and provide the public key.")
                        print(f"   ℹ️  Pass 'builder_space_public_key' parameter with your Space's public key (starts with 'pub-').")
                    print(f"   ℹ️  Site will still work, but visual editing won't be available")

            except Exception as e:
                print(f"   ⚠️  Builder.io setup failed: {str(e)}")
                print(f"   ℹ️  To enable visual editing, create a Space at builder.io and provide the public key.")
                print(f"   ℹ️  Site will still work, but visual editing won't be available")

        # Step 6: Store backup in GCS
        print("\n💾 Storing backup in Cloud Storage...")
        backup_result = store_backup(
            project_name=project_name,
            files=files,
            metadata={
                'industry': industry,
                'features': features,
                'components': components,
                'generation_time': time.time() - start_time
            }
        )

        # Step 7: Log generation metrics
        generation_time = time.time() - start_time
        log_generation(
            project_name=project_name,
            industry=industry,
            components=len(components),
            files=len(files),
            generation_time=generation_time,
            success=True,
            deployment_url=vercel_result.get('staging_url'),
            build_state=vercel_result.get('build_state')
        )

        print(f"\n✨ Generation complete! ({generation_time:.2f}s)")

        # Step 8: Queue provisioning via Pub/Sub
        print("\n📤 Queuing provisioning job...")
        try:
            from darx_core import get_supabase_client

            # Try to get client record from Supabase
            client_id = None
            contact_email = client_info.get('contact_email', 'unknown@example.com')

            try:
                supabase = get_supabase_client()
                if supabase:
                    result = supabase.table('clients')\
                        .select('id, contact_email')\
                        .eq('client_slug', project_name)\
                        .execute()

                    if result.data and len(result.data) > 0:
                        client_id = result.data[0]['id']
                        contact_email = result.data[0].get('contact_email', contact_email)
                        print(f"   ℹ️  Found existing client record: {client_id}")
            except Exception as e:
                print(f"   ℹ️  Could not fetch client from Supabase: {str(e)}")

            # If no client ID found, generate one for the message
            if not client_id:
                import uuid
                client_id = str(uuid.uuid4())
                print(f"   ℹ️  Generated client ID for provisioning: {client_id}")

            # REMOVED: Publishing provisioning message creates infinite loop
            # The provisioner should call the site generator, not vice versa
            # This prevents: provisioner → site-generator → provisioner → site-generator (loop)
            #
            # _publish_provisioning_message({
            #     'client_id': client_id,
            #     'client_slug': project_name,
            #     'client_name': client_info.get('client_name', project_name),
            #     'contact_email': contact_email,
            #     'website_type': client_info.get('website_type', 'marketing'),
            #     'tier': 'entry',
            #     'staging_url': staging_url,
            #     'github_repo': repo_url
            # })

            print(f"   ℹ️  Site generation complete - provisioning should be handled by provisioner service")

        except Exception as e:
            print(f"   ⚠️  Failed during post-deployment step: {str(e)}")
            # Don't fail generation if optional steps fail

        # Return success response
        response = {
            'success': True,
            'project_name': project_name,
            'vercel_project_id': vercel_result.get('vercel_project_id'),
            'staging_url': staging_url,
            'github_repo': repo_url,
            'builder_io_project': builder_space_id,
            'builder_io_url': f'https://builder.io/content?space={builder_space_id}',
            'components_registered': components,
            'generation_time': generation_time,
            'files_generated': len(files)
        }

        return jsonify(response), 200

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        error_type = type(e).__name__

        print(f"\n❌ Generation failed: {error_msg}")
        print(f"Traceback:\n{error_trace}")

        # Extract build logs from Vercel deployment failures
        build_logs = None
        build_state = None
        if "Build logs:" in error_msg:
            # Split error message to extract build logs
            parts = error_msg.split("Build logs:")
            if len(parts) > 1:
                build_logs = parts[1].strip()
                build_state = "ERROR"

        # Analyze error for common patterns and generate helpful context
        help_info = _generate_error_help(error_type, error_msg)

        # Log failure
        log_generation(
            project_name=project_name,
            industry=industry,
            components=0,
            files=0,
            generation_time=time.time() - start_time,
            success=False,
            error=error_msg,
            build_state=build_state,
            build_logs=build_logs
        )

        # Enhanced error response with context
        error_response = {
            'success': False,
            'error': error_msg,
            'error_type': error_type,
            'project_name': project_name,
            'timestamp': time.time(),
            'generation_time': time.time() - start_time,
            'help': help_info
        }

        return jsonify(error_response), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'darx-site-generator'}), 200


@app.route('/edit', methods=['POST', 'OPTIONS'])
def edit():
    """
    HTTP endpoint for editing existing DARX Sites.

    Request body:
    {
        "project_name": "food-asmr-hub",
        "edit_type": "color_palette",
        "changes": {
            "primary": "#FF6B6B",
            "accent": "#4ECDC4"
        }
    }

    Returns:
    {
        "success": true,
        "files_updated": ["app/page.tsx", "tailwind.config.ts"],
        "staging_url": "https://food-asmr-hub.vercel.app",
        "edit_type": "color_palette"
    }
    """

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return _cors_response()

    # Parse request
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        # Log received data for debugging
        print(f"\n📥 Received edit request data: {json.dumps(data, indent=2)}")

        project_name = data.get('project_name')
        edit_type = data.get('edit_type')
        changes = data.get('changes', {})

        if not project_name or not edit_type:
            error_msg = f'Missing required fields: project_name={repr(project_name)}, edit_type={repr(edit_type)}'
            print(f"❌ Validation error: {error_msg}")
            return jsonify({'error': error_msg}), 400

    except Exception as e:
        error_msg = f'Invalid request: {str(e)}'
        print(f"❌ Request parsing error: {error_msg}")
        return jsonify({'error': error_msg}), 400

    print(f"\n✏️  Edit request for: {project_name} ({edit_type})")

    start_time = time.time()

    try:
        # Edit the site
        result = edit_site(
            project_name=project_name,
            edit_type=edit_type,
            changes=changes,
            github_org=GITHUB_ORG
        )

        edit_time = time.time() - start_time

        if result.get('success'):
            print(f"✅ Edit complete! ({edit_time:.2f}s)")
            result['edit_time'] = edit_time
            return jsonify(result), 200
        else:
            print(f"❌ Edit failed: {result.get('error')}")
            return jsonify(result), 500

    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Edit failed: {error_msg}")

        return jsonify({
            'success': False,
            'error': error_msg,
            'project_name': project_name
        }), 500


# ============================================================================
# SITE MANAGEMENT ENDPOINTS - Integration with darx-registry API
# ============================================================================

# darx-registry API URL
REGISTRY_API_URL = os.getenv('REGISTRY_API_URL', 'https://darx-registry-slgtfcnoxq-uc.a.run.app')


def _get_identity_token(audience: str) -> str:
    """
    Get identity token for service-to-service authentication

    Args:
        audience: The URL of the service to call

    Returns:
        ID token string
    """
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    try:
        token = id_token.fetch_id_token(Request(), audience)
        return token
    except Exception as e:
        print(f"Warning: Could not get identity token: {e}")
        return None


def _call_registry_api(endpoint: str, method: str = 'GET', data: Dict = None) -> Dict:
    """
    Call the darx-registry API with service-to-service authentication

    Args:
        endpoint: API endpoint (e.g., '/api/v1/sites')
        method: HTTP method
        data: Request payload for POST/DELETE

    Returns:
        Response JSON
    """
    url = f"{REGISTRY_API_URL}{endpoint}"

    # Get identity token for authentication
    token = _get_identity_token(REGISTRY_API_URL)
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=30)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=30)
        elif method == 'DELETE':
            response = requests.delete(url, json=data, headers=headers, timeout=30)
        else:
            return {'success': False, 'error': f'Unsupported method: {method}'}

        # Try to parse JSON response
        try:
            return response.json()
        except ValueError:
            # If response is not JSON, return error with status and text
            return {
                'success': False,
                'error': f'Non-JSON response from registry (status {response.status_code}): {response.text[:200]}'
            }
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'Registry API error: {str(e)}'}


@app.route('/sites', methods=['GET'])
def list_sites():
    """
    List all sites with optional filters

    Query params:
        - status: Filter by status (active, deleted, all)
        - health_status: Filter by health (healthy, degraded, down)
        - limit: Max results (default 50)
        - offset: Pagination offset
    """
    # Build query string
    params = []
    if request.args.get('status'):
        params.append(f"status={request.args.get('status')}")
    if request.args.get('health_status'):
        params.append(f"health_status={request.args.get('health_status')}")
    if request.args.get('limit'):
        params.append(f"limit={request.args.get('limit')}")
    if request.args.get('offset'):
        params.append(f"offset={request.args.get('offset')}")

    query_string = '&'.join(params)
    endpoint = f"/api/v1/sites?{query_string}" if query_string else "/api/v1/sites"

    result = _call_registry_api(endpoint)
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@app.route('/sites/<client_slug>', methods=['GET'])
def get_site_details(client_slug):
    """
    Get comprehensive details for a specific site

    Returns site data, deployments, health history, and operations
    """
    result = _call_registry_api(f"/api/v1/sites/{client_slug}")

    if result.get('success'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return jsonify(result), status_code


@app.route('/sites/<client_slug>', methods=['DELETE'])
def delete_site(client_slug):
    """
    Soft delete a site with 30-day recovery window

    Request body:
        {
            'deleted_by': 'user@example.com',
            'reason': 'Client requested deletion'
        }
    """
    data = request.get_json()

    if not data or 'deleted_by' not in data:
        return jsonify({
            'success': False,
            'error': 'deleted_by is required'
        }), 400

    result = _call_registry_api(f"/api/v1/sites/{client_slug}", method='DELETE', data=data)
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@app.route('/sites/<client_slug>/recover', methods=['POST'])
def recover_site(client_slug):
    """
    Recover a soft-deleted site within 30-day window

    Request body:
        {
            'recovered_by': 'user@example.com'
        }
    """
    data = request.get_json()

    if not data or 'recovered_by' not in data:
        return jsonify({
            'success': False,
            'error': 'recovered_by is required'
        }), 400

    result = _call_registry_api(f"/api/v1/sites/{client_slug}/recover", method='POST', data=data)
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@app.route('/sites/<client_slug>/health', methods=['GET'])
def get_site_health(client_slug):
    """
    Get current health status for a site
    """
    result = _call_registry_api(f"/api/v1/sites/{client_slug}/health")

    if result.get('success'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return jsonify(result), status_code


@app.route('/sites/<client_slug>/health/check', methods=['POST'])
def check_site_health(client_slug):
    """
    Trigger a health check for a site
    """
    result = _call_registry_api(f"/api/v1/sites/{client_slug}/health/check", method='POST')
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


# ============================================================================


def _publish_provisioning_message(client_data: dict) -> None:
    """
    Publish a Pub/Sub message to trigger provisioner after site generation

    Args:
        client_data: Client information and site details
            Required fields:
            - client_id: UUID of the client
            - client_slug: Client identifier
            - client_name: Client name
            - contact_email: Client email
            - website_type: Type of website
            - tier: Client tier (entry, premium, etc.)
    """
    try:
        # Get GCP project configuration
        gcp_project = os.getenv('GCP_PROJECT', 'sylvan-journey-474401-f9')
        topic_name = 'darx-client-onboarding'

        # Initialize Pub/Sub client
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(gcp_project, topic_name)

        from datetime import datetime

        # Build message payload
        message_data = {
            'clientId': client_data['client_id'],
            'clientSlug': client_data['client_slug'],
            'clientName': client_data['client_name'],
            'contactEmail': client_data['contact_email'],
            'websiteType': client_data.get('website_type', 'marketing'),
            'tier': client_data.get('tier', 'entry'),
            'metadata': {
                'initiatedBy': 'site-generator',
                'onboardingSource': 'darx-generate-website-tool',
                'requestedAt': datetime.utcnow().isoformat(),
                'stagingUrl': client_data.get('staging_url'),
                'githubRepo': client_data.get('github_repo')
            }
        }

        # Publish the message
        message_json = json.dumps(message_data)
        future = publisher.publish(topic_path, message_json.encode('utf-8'))
        future.result()  # Block until publish completes

        print(f"   ✅ Published provisioning message for {client_data['client_slug']}")

    except Exception as e:
        print(f"   ⚠️  Failed to publish provisioning message: {str(e)}")
        # Don't fail the entire generation if Pub/Sub fails
        # Provisioning can be triggered manually if needed


def _cors_response():
    """Handle CORS preflight requests"""
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600'
    }
    return ('', 204, headers)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
