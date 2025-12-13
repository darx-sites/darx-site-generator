"""
Google OAuth Authentication for DARX Site Generator
Provides authentication for onboarding forms and admin access.
"""

import os
from functools import wraps
from flask import session, redirect, url_for, request
from authlib.integrations.flask_client import OAuth

# Allowed users (contact@digitalarchitex.com)
ALLOWED_USERS = [
    'contact@digitalarchitex.com'
]

def init_oauth(app):
    """
    Initialize OAuth with the Flask app

    Args:
        app: Flask application instance

    Returns:
        OAuth instance
    """
    oauth = OAuth(app)

    # Configure Google OAuth
    google = oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

    return oauth, google


def login_required(f):
    """
    Decorator to require authentication for a route
    Redirects to Google Sign-In if not authenticated
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated
        if 'user' not in session:
            # Store the original URL to redirect back after login
            session['next_url'] = request.url
            return redirect(url_for('auth.login'))

        # Check if user is authorized
        user_email = session['user'].get('email')
        if user_email not in ALLOWED_USERS:
            return redirect(url_for('auth.unauthorized'))

        return f(*args, **kwargs)

    return decorated_function


def check_authorized(email):
    """
    Check if an email is authorized to access the service

    Args:
        email: Email address to check

    Returns:
        True if authorized, False otherwise
    """
    return email in ALLOWED_USERS
