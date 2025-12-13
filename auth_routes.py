"""
Authentication Routes for Google OAuth
Handles login, logout, and OAuth callback
"""

from flask import Blueprint, redirect, url_for, session, render_template_string
from auth import check_authorized

# Create auth blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# OAuth instance will be injected by main.py
google = None


def init_auth_routes(google_oauth):
    """
    Initialize auth routes with the Google OAuth client

    Args:
        google_oauth: Authlib Google OAuth client
    """
    global google
    google = google_oauth


@auth_bp.route('/login')
def login():
    """Redirect to Google Sign-In"""
    # Build redirect URI
    redirect_uri = url_for('auth.callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route('/callback')
def callback():
    """Handle OAuth callback from Google"""
    try:
        # Get access token
        token = google.authorize_access_token()

        # Get user info
        user_info = token.get('userinfo')

        if not user_info:
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head><title>Authentication Error</title></head>
            <body>
                <h1>Authentication Error</h1>
                <p>Failed to retrieve user information from Google.</p>
                <a href="{{ url_for('auth.login') }}">Try Again</a>
            </body>
            </html>
            '''), 400

        # Check if user is authorized
        user_email = user_info.get('email')
        if not check_authorized(user_email):
            session['unauthorized_email'] = user_email
            return redirect(url_for('auth.unauthorized'))

        # Store user in session
        session['user'] = {
            'email': user_email,
            'name': user_info.get('name'),
            'picture': user_info.get('picture')
        }

        # Redirect to original URL or home
        next_url = session.pop('next_url', '/')
        return redirect(next_url)

    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head><title>Authentication Error</title></head>
        <body>
            <h1>Authentication Error</h1>
            <p>{{ error }}</p>
            <a href="{{ url_for('auth.login') }}">Try Again</a>
        </body>
        </html>
        ''', error=str(e)), 500


@auth_bp.route('/logout')
def logout():
    """Log out the current user"""
    session.clear()
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head><title>Logged Out</title></head>
    <body>
        <h1>Logged Out</h1>
        <p>You have been successfully logged out.</p>
        <a href="/">Home</a>
    </body>
    </html>
    ''')


@auth_bp.route('/unauthorized')
def unauthorized():
    """Show unauthorized access page"""
    email = session.get('unauthorized_email', 'Unknown')
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Unauthorized Access</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                text-align: center;
            }
            h1 { color: #d32f2f; }
            .email {
                background: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                margin: 20px 0;
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <h1>⛔ Unauthorized Access</h1>
        <p>The email address:</p>
        <div class="email">{{ email }}</div>
        <p>is not authorized to access this service.</p>
        <p>Only <strong>contact@digitalarchitex.com</strong> has access.</p>
        <br>
        <a href="{{ url_for('auth.logout') }}">Sign Out</a>
    </body>
    </html>
    ''', email=email), 403
