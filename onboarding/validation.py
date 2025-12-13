"""
Form Validation for Client Onboarding
"""

import re
from typing import Dict, List, Tuple


def validate_onboarding_form(data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate onboarding form data

    Args:
        data: Form data dictionary

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Required fields
    required_fields = {
        'client_name': 'Client Name',
        'client_slug': 'Client Slug',
        'contact_email': 'Contact Email',
        'website_type': 'Website Type',
        'builder_public_key': 'Builder.io Public Key',
        'builder_private_key': 'Builder.io Private Key'
    }

    for field, label in required_fields.items():
        if not data.get(field, '').strip():
            errors.append(f'{label} is required')

    # Client slug validation
    client_slug = data.get('client_slug', '')
    if client_slug:
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', client_slug) and len(client_slug) > 2:
            errors.append('Client Slug must be lowercase, alphanumeric with hyphens only, and cannot start/end with a hyphen')
        elif len(client_slug) < 3:
            errors.append('Client Slug must be at least 3 characters')
        elif len(client_slug) > 30:
            errors.append('Client Slug must be 30 characters or less')

    # Email validation
    contact_email = data.get('contact_email', '')
    if contact_email:
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, contact_email):
            errors.append('Please enter a valid email address')

    # Website type validation
    valid_website_types = ['marketing', 'ecommerce', 'documentation', 'portfolio', 'blog']
    website_type = data.get('website_type', '')
    if website_type and website_type not in valid_website_types:
        errors.append(f'Website Type must be one of: {", ".join(valid_website_types)}')

    # Builder.io public key validation (accept both legacy and new formats)
    builder_public_key = data.get('builder_public_key', '')
    if builder_public_key:
        # Accept both legacy keys (alphanumeric) and new keys (pub-*)
        # Legacy keys are typically 32-40 characters, new keys start with "pub-"
        if len(builder_public_key) < 20:
            errors.append('Builder.io Public Key appears to be invalid (too short)')
        # Validate format: either starts with "pub-" or is alphanumeric (legacy)
        elif not (builder_public_key.startswith('pub-') or re.match(r'^[a-zA-Z0-9]+$', builder_public_key)):
            errors.append('Builder.io Public Key must be either a legacy key (alphanumeric) or start with "pub-"')

    # Builder.io private key validation
    builder_private_key = data.get('builder_private_key', '')
    if builder_private_key:
        if len(builder_private_key) < 20:
            errors.append('Builder.io Private Key appears to be invalid (too short)')

    return len(errors) == 0, errors


def sanitize_client_slug(slug: str) -> str:
    """
    Sanitize and normalize a client slug

    Args:
        slug: Raw slug input

    Returns:
        Sanitized slug
    """
    # Convert to lowercase
    slug = slug.lower().strip()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)

    # Remove any non-alphanumeric characters (except hyphens)
    slug = re.sub(r'[^a-z0-9-]', '', slug)

    # Remove consecutive hyphens
    slug = re.sub(r'-+', '-', slug)

    # Remove leading/trailing hyphens
    slug = slug.strip('-')

    return slug
