"""
DARX Client Onboarding Module
Handles secure web form for collecting client information and Builder.io credentials.
"""

from .form import onboarding_bp
from .validation import validate_onboarding_form

__all__ = ['onboarding_bp', 'validate_onboarding_form']
