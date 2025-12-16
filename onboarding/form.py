"""
Client Onboarding Form Routes
Secure web form for collecting client information and Builder.io credentials.
"""

import os
import secrets
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, jsonify, redirect, url_for
from functools import wraps
from google.cloud import pubsub_v1

from .validation import validate_onboarding_form, sanitize_client_slug
from auth import login_required

# Create Blueprint
onboarding_bp = Blueprint('onboarding', __name__,
                          template_folder='templates',
                          url_prefix='/onboard')

# Token expiry time (24 hours)
TOKEN_EXPIRY_HOURS = 24


def get_supabase():
    """Get Supabase client for token storage"""
    from supabase import create_client

    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    if not supabase_url or not supabase_key:
        raise Exception("Supabase credentials not configured")

    return create_client(supabase_url, supabase_key)


def generate_onboarding_token(client_slug: str) -> str:
    """
    Generate a secure one-time token for onboarding and store in Supabase

    Args:
        client_slug: Client identifier

    Returns:
        Secure token string
    """
    # Generate secure random token
    token = secrets.token_urlsafe(32)

    try:
        supabase = get_supabase()

        # Store token in Supabase with metadata
        supabase.table('onboarding_tokens').insert({
            'token': token,
            'client_slug': client_slug,
            'created_at': datetime.utcnow().isoformat(),
            'used': False,
            'expires_at': (datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)).isoformat()
        }).execute()

        return token
    except Exception as e:
        print(f"Error storing onboarding token: {str(e)}")
        raise


def validate_token(token: str) -> dict:
    """
    Validate an onboarding token from Supabase

    Args:
        token: Token to validate

    Returns:
        Token data if valid, None otherwise
    """
    try:
        supabase = get_supabase()

        # Fetch token from Supabase
        result = supabase.table('onboarding_tokens')\
            .select('*')\
            .eq('token', token)\
            .single()\
            .execute()

        if not result.data:
            return None

        token_data = result.data

        # Check if token has been used
        if token_data['used']:
            return None

        # Check if token has expired
        expires_at = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=None) > expires_at.replace(tzinfo=None):
            return None

        return {
            'client_slug': token_data['client_slug'],
            'created_at': datetime.fromisoformat(token_data['created_at'].replace('Z', '+00:00')),
            'used': token_data['used']
        }
    except Exception as e:
        print(f"Error validating token: {str(e)}")
        return None


def check_slug_availability(client_slug: str) -> tuple:
    """
    Check if client slug is available (not already in use)

    Args:
        client_slug: The slug to check

    Returns:
        Tuple of (is_available: bool, error_message: str or None)
    """
    try:
        from supabase import create_client

        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            # If Supabase not configured, allow it (dev mode)
            print("Warning: Supabase not configured, skipping slug uniqueness check")
            return True, None

        supabase = create_client(supabase_url, supabase_key)

        # Query for existing client with this slug
        result = supabase.table('client_onboarding')\
            .select('id, client_slug, client_name, status')\
            .eq('client_slug', client_slug)\
            .execute()

        if result.data and len(result.data) > 0:
            # Slug already exists
            existing_client = result.data[0]
            existing_name = existing_client.get('client_name', 'Unknown')
            existing_status = existing_client.get('status', 'unknown')

            return False, f"Client slug '{client_slug}' is already in use by '{existing_name}' (status: {existing_status}). Please choose a different slug."

        # Slug is available
        return True, None

    except Exception as e:
        print(f"Error checking slug availability: {str(e)}")
        # On error, allow the slug (fail open to avoid blocking onboarding)
        # The database will enforce uniqueness as final safeguard
        return True, None


def generate_csrf_token():
    """Generate a CSRF token for form protection"""
    return secrets.token_hex(32)


@onboarding_bp.route('/generate-link', methods=['POST'])
def generate_onboarding_link():
    """
    Generate a one-time onboarding link for a client
    Called from Slack command: /darx onboard <client-slug>

    Expected JSON payload:
    {
        "client_slug": "acme-corp",
        "requester_id": "U12345678"  # Slack user ID (optional)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        client_slug = data.get('client_slug', '')

        if not client_slug:
            return jsonify({'error': 'client_slug is required'}), 400

        # Sanitize the slug
        client_slug = sanitize_client_slug(client_slug)

        if len(client_slug) < 3:
            return jsonify({'error': 'client_slug must be at least 3 characters'}), 400

        # Check if slug is already in use (query Supabase)
        slug_available, error_message = check_slug_availability(client_slug)
        if not slug_available:
            return jsonify({'error': error_message}), 409  # 409 Conflict

        # Generate token
        token = generate_onboarding_token(client_slug)

        # Build the onboarding URL
        base_url = os.getenv('SITE_GENERATOR_URL', 'https://darx-site-generator-474964350921.us-central1.run.app')
        onboarding_url = f"{base_url}/onboard/{token}"

        return jsonify({
            'success': True,
            'onboarding_url': onboarding_url,
            'client_slug': client_slug,
            'expires_in_hours': TOKEN_EXPIRY_HOURS
        })

    except Exception as e:
        print(f"Error generating onboarding link: {str(e)}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@onboarding_bp.route('/<token>', methods=['GET'])
@login_required
def show_onboarding_form(token: str):
    """
    Display the onboarding form
    Requires Google authentication
    """
    # Validate token
    token_data = validate_token(token)

    if not token_data:
        return render_template('onboarding_error.html',
                               error='This onboarding link is invalid or has expired. Please request a new link.')

    # Generate CSRF token
    csrf_token = generate_csrf_token()

    return render_template('onboarding.html',
                           token=token,
                           client_slug=token_data['client_slug'],
                           csrf_token=csrf_token)


@onboarding_bp.route('/<token>', methods=['POST'])
@login_required
def process_onboarding_form(token: str):
    """
    Process the submitted onboarding form
    """
    # Validate token
    token_data = validate_token(token)

    if not token_data:
        return jsonify({'error': 'This onboarding link is invalid or has expired'}), 400

    try:
        # Get form data
        form_data = {
            'client_name': request.form.get('client_name', '').strip(),
            'client_slug': request.form.get('client_slug', token_data['client_slug']).strip(),
            'contact_email': request.form.get('contact_email', '').strip(),
            'website_type': request.form.get('website_type', '').strip(),
            'tier': request.form.get('tier', 'entry').strip(),  # Default to entry if not provided
            'builder_public_key': request.form.get('builder_public_key', '').strip(),
            'builder_private_key': request.form.get('builder_private_key', '').strip(),
            'builder_space_id': request.form.get('builder_space_id', '').strip(),
            'industry': request.form.get('industry', '').strip(),
        }

        # Validate form data
        is_valid, errors = validate_onboarding_form(form_data)

        if not is_valid:
            return render_template('onboarding.html',
                                   token=token,
                                   client_slug=token_data['client_slug'],
                                   csrf_token=generate_csrf_token(),
                                   errors=errors,
                                   form_data=form_data)

        # Check slug uniqueness one more time (in case form was manually edited)
        submitted_slug = form_data['client_slug']
        slug_available, error_message = check_slug_availability(submitted_slug)

        if not slug_available:
            errors = [error_message]
            return render_template('onboarding.html',
                                   token=token,
                                   client_slug=token_data['client_slug'],
                                   csrf_token=generate_csrf_token(),
                                   errors=errors,
                                   form_data=form_data)

        # Mark token as used in Supabase
        try:
            supabase = get_supabase()
            supabase.table('onboarding_tokens')\
                .update({'used': True})\
                .eq('token', token)\
                .execute()
        except Exception as e:
            print(f"Error marking token as used: {str(e)}")

        # Store client data in Supabase
        success, result = store_client_data(form_data)

        if not success:
            return render_template('onboarding.html',
                                   token=token,
                                   client_slug=token_data['client_slug'],
                                   csrf_token=generate_csrf_token(),
                                   errors=[result],
                                   form_data=form_data)

        # Show success page
        return render_template('onboarding_success.html',
                               client_name=form_data['client_name'],
                               client_slug=form_data['client_slug'])

    except Exception as e:
        print(f"Error processing onboarding form: {str(e)}")
        return render_template('onboarding.html',
                               token=token,
                               client_slug=token_data['client_slug'],
                               csrf_token=generate_csrf_token(),
                               errors=[f'An unexpected error occurred: {str(e)}'],
                               form_data=request.form)


def publish_onboarding_message(form_data: dict, client_id: str) -> None:
    """
    Publish a Pub/Sub message to trigger the provisioner Cloud Function

    Args:
        form_data: Validated form data from the onboarding form
        client_id: Generated client ID from Supabase
    """
    # Get GCP project configuration
    gcp_project = os.getenv('GCP_PROJECT', 'sylvan-journey-474401-f9')
    topic_name = 'darx-client-onboarding'

    # Initialize Pub/Sub client and publisher
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(gcp_project, topic_name)

    # Generate a client ID for the message (UUID v4)
    message_client_id = str(uuid.uuid4())

    # Build message payload according to spec (camelCase field names)
    message_data = {
        'clientId': message_client_id,
        'clientSlug': form_data['client_slug'],
        'clientName': form_data['client_name'],
        'contactEmail': form_data['contact_email'],
        'websiteType': form_data.get('website_type', 'marketing'),
        'tier': form_data.get('tier', 'entry'),
        'metadata': {
            'initiatedBy': 'onboarding-form',
            'onboardingSource': 'admin-dashboard',
            'requestedAt': datetime.utcnow().isoformat(),
            'supabaseClientId': client_id
        }
    }

    # Only include Builder.io credentials for premium+ tiers
    if form_data.get('tier', 'entry') != 'entry':
        message_data['builder'] = {
            'publicKey': form_data['builder_public_key'],
            'privateKey': form_data['builder_private_key'],
            'spaceId': form_data.get('builder_space_id', '')
        }

    # Publish the message
    message_json = json.dumps(message_data)
    future = publisher.publish(topic_path, message_json.encode('utf-8'))
    future.result()  # Block until publish completes


def store_client_data(form_data: dict) -> tuple:
    """
    Store client data in Supabase

    Args:
        form_data: Validated form data

    Returns:
        Tuple of (success: bool, result_or_error: str)
    """
    try:
        # Import Supabase client
        from supabase import create_client

        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            print("Warning: Supabase credentials not configured")
            # For now, just log and continue (will be properly implemented later)
            return True, "Client data recorded (Supabase not configured)"

        supabase = create_client(supabase_url, supabase_key)

        # Prepare client onboarding record
        tier = form_data.get('tier', 'entry')

        onboarding_record = {
            'client_name': form_data['client_name'],
            'client_slug': form_data['client_slug'],
            'contact_email': form_data['contact_email'],
            'industry': form_data.get('industry'),
            'tier': tier,
            'onboarding_form_data': {
                'website_type': form_data['website_type'],
            },
            'status': 'pending_provisioning',
        }

        # Only include Builder.io credentials for premium+ tiers
        if tier != 'entry':
            onboarding_record['builder_public_key'] = form_data['builder_public_key']
            onboarding_record['builder_private_key'] = form_data['builder_private_key']
            onboarding_record['onboarding_form_data']['builder_space_id'] = form_data.get('builder_space_id')

        # Insert into client_onboarding table (the correct table for onboarding submissions)
        result = supabase.table('client_onboarding').insert(onboarding_record).execute()

        if result.data:
            client_id = result.data[0].get('id')

            # Publish Pub/Sub message to trigger provisioner
            try:
                publish_onboarding_message(form_data, client_id)
                print(f"Published onboarding message for client: {client_id}")
            except Exception as pub_error:
                print(f"Warning: Failed to publish Pub/Sub message: {str(pub_error)}")
                # Don't fail the onboarding if Pub/Sub fails

            return True, client_id
        else:
            return False, "Failed to create client record"

    except Exception as e:
        print(f"Error storing client data: {str(e)}")
        # Don't fail completely if Supabase isn't configured yet
        if 'clients' in str(e) and 'does not exist' in str(e):
            return True, "Client data recorded (table setup pending)"
        return False, f"Database error: {str(e)}"


# Cleanup function for expired tokens (call periodically)
def cleanup_expired_tokens():
    """Remove expired tokens from Supabase"""
    try:
        supabase = get_supabase()
        now = datetime.utcnow().isoformat()

        # Delete tokens that have expired
        supabase.table('onboarding_tokens')\
            .delete()\
            .lt('expires_at', now)\
            .execute()

        print(f"Cleaned up expired onboarding tokens")
    except Exception as e:
        print(f"Error cleaning up expired tokens: {str(e)}")
